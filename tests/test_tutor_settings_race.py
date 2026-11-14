"""A delayed settings response must not erase a newer tutor reply."""
import json,tempfile,threading,unittest
from pathlib import Path
from dashboard.app import make_server
from storage.database import Database
from utils.config import DEFAULT_CONFIG,save_config
try:
    from playwright.sync_api import sync_playwright,expect
except ImportError:sync_playwright=None


@unittest.skipUnless(sync_playwright,'requires isolated Edge QA')
class TutorSettingsRaceTests(unittest.TestCase):
    def test_message_waits_for_mode_save(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=Database(root/'qa.db');db.initialize();db.create_subject('Lógica sintética');save_config(json.loads(DEFAULT_CONFIG.read_text(encoding='utf8')),root/'config.json')
            def provider(*unused):
                def c(text):return {'text':text,'basis':'general','references':[]}
                return json.dumps({'concept':c('E exige todas as condições.'),'usefulness':c('Ajuda a combinar regras.'),'example':c('True and False resulta em False.')})
            server=make_server(db,0,config_path=root/'config.json',tutor_provider=provider);thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(channel='msedge',headless=True)
                    try:
                        page=browser.new_page();page.add_init_script("""const original=window.fetch;window.fetch=async function(input,init){const response=await original(input,init);if(init?.method==='PATCH'&&JSON.parse(init.body||'{}').mode){await new Promise(r=>setTimeout(r,1500));}return response;};""")
                        page.goto(f'http://127.0.0.1:{server.server_port}');page.locator('nav a[data-view-target="estudar"]').click()
                        page.wait_for_function("document.querySelector('#tutor-thread').value.length>0")
                        page.locator('#tutor-mode').select_option('aula');page.locator('#tutor-draft').fill('Ensine lógica booleana');page.locator('#tutor-send').click()
                        expect(page.locator('#tutor-history .assistant')).to_have_count(1)
                        page.wait_for_timeout(1800)
                        expect(page.locator('#tutor-history .assistant')).to_have_count(1)
                    finally:browser.close()
            finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()
