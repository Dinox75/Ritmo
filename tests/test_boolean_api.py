import json
import tempfile
import threading
import unittest
import urllib.request
import urllib.error
from pathlib import Path


class BooleanAPITests(unittest.TestCase):
    def test_launcher_refuses_unmarked_existing_database(self):
        from scripts.open_boolean_lesson import validate_sandbox
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);(root/'ritmo.db').write_bytes(b'foreign database sentinel')
            with self.assertRaises(ValueError):validate_sandbox(root)
            self.assertEqual((root/'ritmo.db').read_bytes(),b'foreign database sentinel')

    def test_flag_routes_origin_and_persistence(self):
        from storage.database import Database
        from dashboard.app import make_server
        from utils.config import DEFAULT_CONFIG,save_config
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);db=Database(root/'qa.db');db.initialize()
            config=json.loads(DEFAULT_CONFIG.read_text(encoding='utf8'));save_config(config,root/'config.json')
            server=make_server(db,0,config_path=root/'config.json');thread=threading.Thread(target=server.serve_forever);thread.start()
            base=f'http://127.0.0.1:{server.server_port}';opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
            def call(path='',data=None,origin=None):
                headers={'Content-Type':'application/json'}
                if origin:headers['Origin']=origin
                request=urllib.request.Request(base+'/api/boolean-lesson'+path,json.dumps(data).encode() if data is not None else None,headers)
                with opener.open(request) as response:return json.load(response)
            try:
                self.assertFalse(call()['enabled'])
                with self.assertRaises(urllib.error.HTTPError) as disabled:call(data={'scenario':'negation_true'})
                self.assertEqual(disabled.exception.code,400)
                config['experiments']={'boolean_lesson':True};save_config(config,root/'config.json')
                with self.assertRaises(urllib.error.HTTPError) as external:call(data={'scenario':'negation_true'},origin='https://example.org')
                self.assertEqual(external.exception.code,403)
                state=call(data={'scenario':'negated_conjunction'});self.assertEqual(state['stage'],'concept');self.assertNotIn('_task',state)
                self.assertEqual(state['scenario'],'negated_conjunction')
                self.assertNotIn('expected',state)
                self.assertEqual(call('/'+state['id'])['id'],state['id'])
            finally:server.shutdown();server.server_close();server.tutor_runtime.stop();thread.join()
