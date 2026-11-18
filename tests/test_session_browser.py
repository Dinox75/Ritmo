import tempfile
import threading
import unittest
from pathlib import Path
from dashboard.app import make_server
from storage.database import Database
from tests.browser_target import BROWSER
from playwright.sync_api import sync_playwright, expect


@unittest.skipUnless(BROWSER, 'Edge/Chromium needed')
class AuthorizedBrowserTests(unittest.TestCase):
    def test_browser_must_enter_one_time_code_and_code_is_not_in_static_resources(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Database(Path(folder)/'qa.db');db.initialize()
            server=make_server(db,0);thread=threading.Thread(target=server.serve_forever);thread.start()
            try:
                with sync_playwright() as pw:
                    browser=pw.chromium.launch(executable_path=str(BROWSER),headless=True)
                    try:
                        page=browser.new_page();base=f'http://127.0.0.1:{server.server_port}'
                        page.goto(base+'/authorize.html')
                        page.locator('#code').fill('invalid');page.locator('button').click()
                        expect(page.locator('#error')).to_contain_text('inválido')
                        code=server.session.issue_code()
                        self.assertNotIn(code,page.content());self.assertNotIn(server.session.token,page.content())
                        page.locator('#code').fill(code);page.locator('button').click()
                        expect(page.locator('#view-inicio')).to_be_visible()
                        self.assertNotIn(code,page.url)
                        self.assertNotIn(server.session.token,page.content())
                        page.reload();expect(page.locator('#view-inicio')).to_be_visible()
                    finally:browser.close()
            finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()
