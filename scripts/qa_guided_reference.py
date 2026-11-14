"""Isolated real-data Edge QA for the guided-reference panel."""
import argparse
import json
import sys
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from training.lab.panel import make_server


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result=json.loads((a.run/'guided-reference.json').read_text(encoding='utf8'))
    assert result['complete'] and len(result['cases'])==9
    assert all(not v['assessment']['corpus_eligible'] and not v['observer']['decision_authority'] for c in result['cases'] for v in c['versions'].values())
    server=make_server(a.run,0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();rows=[]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for width in (390,1366,1920):
                    page=browser.new_page(viewport={'width':width,'height':1000});errors=[]
                    page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}')
                    panel=page.locator('#guided-reference');panel.wait_for()
                    assert panel.locator(':scope > details').count()==9
                    assert panel.locator('.triple > div').count()==27
                    assert panel.locator('table').count()==3
                    first=panel.locator(':scope > details').first
                    first.locator(':scope > summary').click();page.wait_for_timeout(3300)
                    assert panel.locator(':scope > details').first.get_attribute('open') is None
                    first.locator(':scope > summary').focus();page.keyboard.press('Space')
                    assert first.get_attribute('open') is not None
                    audit=first.locator('.triple details').first
                    audit.locator('summary').click();page.wait_for_timeout(3300)
                    assert first.locator('.triple details').first.get_attribute('open') is not None
                    first.locator('.triple details').first.locator('summary').click()
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth')
                    assert not errors,errors
                    page.screenshot(path=str(a.output/f'guided-{width}.png'),full_page=True)
                    first.scroll_into_view_if_needed()
                    page.evaluate("window.scrollTo(0,document.querySelector('#guided-reference > details').getBoundingClientRect().top+scrollY-20)")
                    page.screenshot(path=str(a.output/f'comparison-{width}.png'))
                    rows.append({'width':width,'result':'passed','versions':27,'tables':3,'overflow':False,'js_errors':errors,'keyboard':'passed','refresh_state':'passed'})
                    page.close()
            finally:browser.close()
    finally:server.shutdown();server.server_close();thread.join()
    (a.output/'qa.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows))


if __name__=='__main__':main()
