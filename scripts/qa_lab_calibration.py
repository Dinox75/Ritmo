"""Read-only real calibration panel QA in isolated Edge."""
import argparse
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from training.lab.panel import make_server


def main():
    p = argparse.ArgumentParser(); p.add_argument('--run', type=Path, required=True); p.add_argument('--output', type=Path, required=True)
    a = p.parse_args(); a.output.mkdir(parents=True, exist_ok=True)
    result = json.loads((a.run / 'calibration.json').read_text(encoding='utf8'))
    assert result['replay']['complete'] and len(result['replay']['rows']) == 60
    assert not result['generation_pilot_allowed'] and not result['new_generation_executed']
    server = make_server(a.run, 0); thread = threading.Thread(target=server.serve_forever, daemon=True); thread.start()
    rows = []
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser = pw.chromium.launch(channel='msedge', headless=True)
            try:
                for width in (390,1366,1920):
                    page = browser.new_page(viewport={'width': width, 'height': 1000})
                    errors = []; page.on('pageerror', lambda e: errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    page.locator('#calibration').get_by_text('A avaliação ainda precisa de correção', exact=True).wait_for()
                    assert page.locator('#calibration details').count() == 96
                    assert page.locator('#calibration table').count() == 3
                    assert 'aprovação integral' in page.locator('#calibration').inner_text()
                    detail = page.locator('#calibration details').first
                    detail.locator('summary').click()
                    page.wait_for_timeout(3300)
                    assert page.locator('#calibration details').first.get_attribute('open') is not None
                    page.locator('#calibration details').first.locator('summary').click()
                    assert not page.evaluate('document.documentElement.scrollWidth > innerWidth')
                    assert not errors, errors
                    page.screenshot(path=str(a.output / f'calibration-{width}.png'), full_page=True)
                    rows.append({'width':width,'result':'passed','details':96,'js_errors':errors,'overflow':False})
                    page.close()
            finally: browser.close()
    finally: server.shutdown(); server.server_close(); thread.join()
    (a.output / 'qa.json').write_text(json.dumps(rows, indent=2), encoding='utf8')
    print(json.dumps(rows))


if __name__ == '__main__': main()
