import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch
from dashboard.app import make_server
from storage.database import Database


class SessionSecurityTests(unittest.TestCase):
    def test_sensitive_routes_require_session_even_without_origin(self):
        with tempfile.TemporaryDirectory() as folder:
            db = Database(Path(folder) / 'qa.db'); db.initialize()
            erased = threading.Event()
            server = make_server(db, 0, on_erase=erased.set)
            thread = threading.Thread(target=server.serve_forever); thread.start()
            base = f'http://127.0.0.1:{server.server_port}'
            def request(path, data=None, headers=None):
                return urllib.request.urlopen(urllib.request.Request(base + path,
                    json.dumps(data).encode() if data is not None else None,
                    {'Content-Type':'application/json', **(headers or {})}), timeout=5)
            try:
                for headers in ({}, {'Cookie':'ritmo_session=invalid'}, {'Authorization':'Bearer invalid'}):
                    for path, data in [('/api/subjects',None),('/api/config',None),('/api/diagnostics',None),
                                       ('/api/subjects',{'name':'attack'}),('/api/app/erase',{'confirmation':'APAGAR'})]:
                        with self.assertRaises(urllib.error.HTTPError) as error:
                            request(path,data,headers)
                        self.assertEqual(error.exception.code,401)
                self.assertFalse(erased.is_set()); self.assertEqual(db.list_subjects(),[])
                auth = {'Authorization':'Bearer ' + server.session.token}
                with self.assertRaises(urllib.error.HTTPError) as error:
                    request('/api/subjects',headers={**auth,'Origin':'https://evil.example'})
                self.assertEqual(error.exception.code,403)
                with request('/api/subjects',headers=auth) as response:self.assertEqual(json.load(response),[])
                code = server.session.issue_code()
                with request('/api/session',{'code':code}) as response:
                    cookie = response.headers['Set-Cookie']; self.assertIn('HttpOnly',cookie);self.assertIn('SameSite=Strict',cookie)
                with request('/api/config',headers={'Cookie':cookie.split(';')[0]}) as response:self.assertEqual(response.status,200)
                with self.assertRaises(urllib.error.HTTPError):request('/api/session',{'code':code})
                with self.assertRaises(urllib.error.HTTPError):request('/api/session',{'code':server.session.issue_code()}, {'Origin':'https://evil.example'})
            finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()

    def test_native_cancel_never_sets_erase_or_closes(self):
        from desktop import DesktopApp
        app = DesktopApp()
        with patch('desktop.confirm_erase_native',return_value=False), patch.object(app,'request_close') as close:
            app.request_erase()
            self.assertFalse(app.erase_requested);close.assert_not_called()
        with patch('desktop.confirm_erase_native',return_value=True),patch.object(app,'request_close') as close:
            app.request_erase();self.assertTrue(app.erase_requested);close.assert_called_once()
