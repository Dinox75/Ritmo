"""Synthetic browser startup diagnostic; no personal DB or model inference."""
import argparse,json,sys,tempfile,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage.database import Database
from dashboard.app import make_server
from utils.config import DEFAULT_CONFIG,save_config


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);p.add_argument('--runs',type=int,default=10);a=p.parse_args();rows=[]
    with tempfile.TemporaryDirectory() as f:
        root=Path(f);db=Database(root/'qa.db');db.initialize();save_config(json.loads(DEFAULT_CONFIG.read_text(encoding='utf8')),root/'config.json')
        server=make_server(db,0,config_path=root/'config.json');thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                try:
                    for i in range(a.runs):
                        page=browser.new_page();failures=[];page.on('requestfailed',lambda r:failures.append({'url':r.url,'error':r.failure}))
                        page.goto(f'http://127.0.0.1:{server.server_port}/');page.wait_for_timeout(900)
                        rows.append({'run':i,'request_queue_size':server.request_queue_size,'failures':list(failures),'initial_error':'Não foi possível carregar o Ritmo' in page.locator('body').inner_text()});page.close()
                finally:browser.close()
        finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()
    a.output.write_text(json.dumps(rows,indent=2),encoding='utf8');print(json.dumps(rows));assert not any(x['initial_error'] for x in rows)


if __name__=='__main__':main()
