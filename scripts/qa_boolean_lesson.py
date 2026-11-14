"""Real isolated UI flow with synthetic attempts; not student learning evidence."""
import argparse
import json
import sys
import tempfile
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage.database import Database
from dashboard.app import make_server
from utils.config import DEFAULT_CONFIG,save_config
from tutor.boolean_lesson import scenarios


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);results=[]
    with tempfile.TemporaryDirectory(prefix='boolean-ui-') as folder:
        root=Path(folder);db=Database(root/'qa.db');db.initialize();config=json.loads(DEFAULT_CONFIG.read_text(encoding='utf8'));save_config(config,root/'config.json')
        server=make_server(db,0,config_path=root/'config.json');thread=threading.Thread(target=server.serve_forever);thread.start()
        try:
            from playwright.sync_api import sync_playwright,expect
            with sync_playwright() as pw:
                browser=pw.chromium.launch(channel='msedge',headless=True)
                try:
                    page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/boolean-lesson.html');expect(page.locator('#availability')).to_contain_text('Modo desligado');expect(page.locator('#controls')).to_be_hidden();page.close()
                    config['experiments']={'boolean_lesson':True};save_config(config,root/'config.json')
                    for width in (390,1366,1920):
                        page=browser.new_page(viewport={'width':width,'height':1000});errors=[];page.on('pageerror',lambda e:errors.append(str(e)))
                        page.goto(f'http://127.0.0.1:{server.server_port}/boolean-lesson.html');expect(page.locator('#controls')).to_be_visible()
                        for key,t in scenarios().items():
                            page.locator('#scenario').select_option(t['family']);page.locator('#start').click();expect(page.locator('#stage')).to_contain_text('Conceito')
                            page.locator('#continue').focus();page.keyboard.press('Enter');expect(page.locator('#stage')).to_contain_text('Exemplo curto')
                            page.locator('#continue').click();expect(page.locator('#stage')).to_contain_text('Primeira tentativa')
                            name,value=next(iter(t['values'].items()))
                            def submit(expr,conclusion):
                                page.locator('#fact-name').select_option(name);page.locator('#fact-value').select_option(str(value));page.locator('#expression').fill(expr);page.locator('#conclusion').select_option(str(conclusion));page.locator('#submit-attempt').click()
                            submit(t['mistake'],not t['expected']);expect(page.locator('#stage')).to_contain_text('Dica e nova tentativa')
                            page.reload();expect(page.locator('#stage')).to_contain_text('Dica e nova tentativa')
                            submit(t['expression'],t['expected']);expect(page.locator('#stage')).to_contain_text('Correção fundamentada');expect(page.locator('#dialog')).to_contain_text('Retomando a primeira tentativa')
                            page.locator('#continue').click();expect(page.locator('#stage')).to_contain_text('Exercício de transferência')
                            tr=t['transfer'];name,value=next(iter(tr['values'].items()));submit(tr['expression'],tr['expected']);expect(page.locator('#stage')).to_contain_text('Verificação concluída')
                            page.locator('#question-form').locator('xpath=..').locator('summary').click();page.locator('#question').fill('Qual a probabilidade de chover amanhã?');page.locator('#question-form button').click();expect(page.locator('#dialog')).to_contain_text('Não consigo verificar')
                            assert not page.evaluate('document.documentElement.scrollWidth>innerWidth');assert not errors,errors
                            if key=='negation_true':page.screenshot(path=str(a.output/f'boolean-lesson-{width}.png'),full_page=True)
                        if width==1920:
                            page.locator('#quit').click();expect(page.locator('#availability')).to_contain_text('Instância encerrando')
                        results.append({'width':width,'result':'passed','flows':3,'reopen':'passed','keyboard':'passed','outside_scope':'passed','overflow':False,'errors':errors});page.close()
                finally:browser.close()
        finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()
        import socket
        with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',server.server_port))!=0
    (a.output/'qa.json').write_text(json.dumps({'tests':results,'default_disabled':True,'quit_button':True,'port_released':True,'temporary_database':True,'student_learning_evidence':False},indent=2),encoding='utf8');print(json.dumps(results))


if __name__=='__main__':main()
