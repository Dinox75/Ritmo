"""Open a read-only lab panel without a terminal; never launches training."""
import argparse
import ctypes
import json
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--port', type=int, default=8765); args = p.parse_args()
    repo = Path(__file__).resolve().parents[1]
    args.run.mkdir(parents=True, exist_ok=True)
    url = f'http://127.0.0.1:{args.port}'
    def ready():
        try:
            with urllib.request.urlopen(url + '/api', timeout=2) as response: value = json.load(response)
            local = args.run / 'state.json'
            if local.exists() and value['state'].get('fingerprint') != json.loads(local.read_text(encoding='utf8'))['fingerprint']:
                raise RuntimeError('A porta já atende outro laboratório. Escolha outra porta; nenhum processo foi encerrado.')
            return True
        except (OSError, ValueError, KeyError): return False
    if not ready():
        with (args.run / 'panel-launch.log').open('a', encoding='utf8') as log:
            subprocess.Popen([sys.executable, '-m', 'training.lab.panel', '--run', str(args.run), '--port', str(args.port)],
                             cwd=repo, stdout=log, stderr=subprocess.STDOUT,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        for _ in range(30):
            if ready(): break
            time.sleep(.2)
        else: raise RuntimeError('Não foi possível abrir o painel. Consulte ' + str(args.run / 'panel-launch.log'))
    webbrowser.open(url)


if __name__ == '__main__':
    try: main()
    except Exception as error:
        if sys.platform == 'win32': ctypes.windll.user32.MessageBoxW(None, str(error), 'Ritmo · Laboratório', 0x10)
        else: raise
