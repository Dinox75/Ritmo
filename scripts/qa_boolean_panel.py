"""Read-only comparison panel QA, synthetic complete dialogues."""
import argparse,json,sys,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from training.lab.panel import make_server


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    result=json.loads((a.run/'lesson-comparison.json').read_text(encoding='utf8'));assert result['complete'] and all(c['assessment'] for c in result['cases'])
    server=make_server(a.run,0);thread=threading.Thread(target=server.serve_forever);thread.start();rows=[]
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as pw:
            browser=pw.chromium.launch(channel='msedge',headless=True)
            try:
                for width in (390,1366,1920):
                    page=browser.new_page(viewport={'width':width,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}');panel=page.locator('#lesson-flow');panel.wait_for()
                    assert panel.locator(':scope > details').count()==3
                    assert panel.locator('.pair > div').count()==6
                    assert panel.locator('.pair article').count()==81
                    first=panel.locator(':scope > details').first;first.locator(':scope > summary').click();page.wait_for_timeout(3300)
                    assert first.get_attribute('open') is None
                    first.locator(':scope > summary').focus();page.keyboard.press('Enter');assert first.get_attribute('open') is not None
                    assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not errors,errors
                    page.screenshot(path=str(a.output/f'panel-{width}.png'))
                    first.locator('.pair').scroll_into_view_if_needed()
                    page.evaluate("window.scrollTo(0,document.querySelector('#lesson-flow .pair').getBoundingClientRect().top+scrollY-15)")
                    page.screenshot(path=str(a.output/f'dialog-{width}.png'))
                    rows.append({'width':width,'result':'passed','complete_messages':81,'overflow':False,'errors':errors,'details_state':'passed'});page.close()
            finally:browser.close()
    finally:server.shutdown();server.server_close();thread.join()
    (a.output/'qa.json').write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows))


if __name__=='__main__':main()
