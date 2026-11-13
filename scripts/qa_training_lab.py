"""Isolated Edge QA: real run data; no personal browser profile/database."""
import argparse
import json
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.panel import make_server


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--generation', action='store_true'); args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = make_server(args.run, 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    results = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for width in (390, 1366, 1920):
                    page = browser.new_page(viewport={'width': width, 'height': 1000})
                    errors = []; page.on('pageerror', lambda error: errors.append(str(error)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.locator('#status').filter(has_text='Concluído' if args.generation else 'Bloqueado').wait_for()
                    assert page.locator('#approval').inner_text() == 'Não avaliado — sem treino real'
                    assert page.locator('#sources table tr').count() == (7 if args.generation else 6)
                    assert not page.locator('#simulation').is_visible()
                    overflow = page.evaluate('document.documentElement.scrollWidth > window.innerWidth')
                    assert not overflow, f'overflow at {width}'
                    page.locator('#candidates summary').first.click()
                    assert page.locator('#candidates details').first.get_attribute('open') is not None
                    if args.generation:
                        assert page.locator('#family-results table tr').count() == 11
                        assert page.locator('#kind-results p').count() == 3
                        assert page.locator('#generation-status').inner_text().startswith('Anterior: 0/30')
                        page.wait_for_timeout(3300)
                        assert page.locator('#candidates details').first.get_attribute('open') is not None
                        page.locator('#candidates summary').first.click()
                    page.screenshot(path=str(args.output / f'training-lab-{width}.png'), full_page=True)
                    assert not errors, errors
                    results.append({'width': width, 'status': 'passed', 'overflow': overflow, 'js_errors': errors})
                    page.close()
            finally: browser.close()
    finally: server.shutdown(); server.server_close(); thread.join()
    (args.output / 'qa.json').write_text(json.dumps(results, indent=2) + '\n', encoding='utf8')
    print(json.dumps(results))


if __name__ == '__main__': main()
