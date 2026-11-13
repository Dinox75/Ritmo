"""Read-only loopback panel. SSH forwarding: ssh -L 8765:127.0.0.1:8765 user@host."""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .state import view


def make_server(root, port=8765):
    root = Path(root).resolve()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args): pass
        def send(self, status, data, content='application/json; charset=utf-8'):
            self.send_response(status)
            self.send_header('Content-Type', content)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Content-Security-Policy', "default-src 'self'; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'; connect-src 'self'")
            self.end_headers(); self.wfile.write(data)
        def do_GET(self):
            if self.headers.get('Host') not in {f'127.0.0.1:{self.server.server_port}', f'localhost:{self.server.server_port}'}:
                self.send(403, b'{}'); return
            if self.path in {'/', '/panel.js'}:
                path = Path(__file__).parent / ('panel.html' if self.path == '/' else 'panel.js')
                self.send(200, path.read_bytes(), 'text/html; charset=utf-8' if self.path == '/' else 'text/javascript; charset=utf-8'); return
            if self.path != '/api': self.send(404, b'{}'); return
            def load(name, default):
                try: return json.loads((root / name).read_text(encoding='utf-8'))
                except (OSError, ValueError): return default
            state = load('state.json', {'status': 'waiting', 'message': 'Aguardando execução da CLI.'})
            sources = load('sources.json', {'accepted': [], 'refused': []})
            sources['accepted'] = [{k: v for k, v in s.items() if k != 'text'} for s in sources['accepted']]
            candidates = load('candidates.json', [])
            for row in candidates:
                for key in ('matter', 'pedagogy'):
                    if row.get('candidate', {}).get(key): row['candidate'][key].pop('text', None)
            generation = load('generation-comparison.json', None)
            if generation:
                for pair in generation['pairs']:
                    for method in ('legacy', 'two_stage'):
                        for key in ('matter', 'pedagogy'):
                            pair.get(method, {}).get('candidate', {}).get(key, {}).pop('text', None)
            payload = {'state': view(state), 'sources': sources, 'candidates': candidates,
                       'generation': generation,
                       'training': load('training/progress.json', {}),
                       'comparison': load('training/comparison.json', None)}
            self.send(200, json.dumps(payload, ensure_ascii=False).encode())
        def do_POST(self): self.send(405, b'{}')
        do_PUT = do_DELETE = do_PATCH = do_POST
    return ThreadingHTTPServer(('127.0.0.1', port), Handler)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run', type=Path, required=True); p.add_argument('--port', type=int, default=8765)
    args = p.parse_args()
    with make_server(args.run, args.port) as server:
        print(f'Painel privado: http://127.0.0.1:{server.server_port}', flush=True)
        try: server.serve_forever()
        except KeyboardInterrupt: pass


if __name__ == '__main__': main()
