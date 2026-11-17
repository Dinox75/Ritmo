"""Negative API probes + real native erase cancellation; synthetic data only."""
import argparse
import ctypes
import json
import tempfile
import time
import urllib.request
import urllib.error
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from qa_packaged_windows import launch, authorize, quit_and_verify, EDGE


def run(exe):
    report={'synthetic':True,'negative_requests':[],'native_confirmation':False}
    with tempfile.TemporaryDirectory(prefix='ritmo-security-',ignore_cleanup_errors=True) as folder:
        root=Path(folder);data=root/'Ritmo';data.mkdir()
        (data/'.migration_disabled').write_text('1')
        config=json.loads((Path(__file__).resolve().parents[1]/'config/config.json').read_text(encoding='utf8'))
        config['tutor']['model_root']=str(root/'no-models')
        (data/'config.json').write_text(json.dumps(config),encoding='utf8')
        process=None
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=str(EDGE),headless=True)
            try:
                process,port=launch(exe,root);base=f'http://127.0.0.1:{port}'
                for name,headers in [('none',{}),('invalid',{'Cookie':'ritmo_session=invalid'}),('external',{'Origin':'https://evil.example'})]:
                    for path,body in [('/api/config',None),('/api/subjects',None),('/api/notes',None),
                                      ('/api/diagnostics',None),('/api/backup',{}),
                                      ('/api/app/quit',{}),('/api/app/erase',{'confirmation':'APAGAR'})]:
                        request=urllib.request.Request(base+path, json.dumps(body).encode() if body is not None else None,
                                                       {'Content-Type':'application/json',**headers})
                        try:urllib.request.urlopen(request,timeout=5);raise AssertionError('Unauthorized request accepted')
                        except urllib.error.HTTPError as error:
                            assert error.code==(403 if name=='external' else 401)
                            report['negative_requests'].append({'client':name,'route':path,'status':error.code})
                assert process.poll() is None
                page=browser.new_page();authorize(page,process,port);page.goto(base)
                expect(page.locator('#view-inicio')).to_be_visible()
                reply=page.evaluate("async()=>{const r=await fetch('/api/app/erase',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({confirmation:'APAGAR'})});return await r.json()}")
                assert reply['confirmation_requested']
                user32=ctypes.windll.user32;user32.FindWindowW.restype=ctypes.c_void_p
                user32.GetDlgItem.restype=ctypes.c_void_p
                deadline=time.monotonic()+15;handle=None
                while time.monotonic()<deadline:
                    handle=user32.FindWindowW(None,'Ritmo · apagar dados pessoais')
                    if handle:break
                    time.sleep(.1)
                assert handle,'Native confirmation did not appear'
                # Never click Yes in this test. IDNO=7 is the native refusal.
                button=user32.GetDlgItem(ctypes.c_void_p(handle),7)
                assert button,'Native No button missing'
                user32.SendMessageW(ctypes.c_void_p(button),0x00F5,0,0)
                deadline=time.monotonic()+5
                while user32.FindWindowW(None,'Ritmo · apagar dados pessoais') and time.monotonic()<deadline:time.sleep(.1)
                assert not user32.FindWindowW(None,'Ritmo · apagar dados pessoais')
                assert process.poll() is None and (data/'ritmo.db').is_file()
                assert page.evaluate("async()=> (await fetch('/api/subjects')).status")==200
                report.update(native_confirmation=True,cancel_preserved_database=True,cancel_kept_app_open=True)
                quit_and_verify(page,process,port);process=None;report['port_released']=True
            finally:
                browser.close()
                if process is not None and process.poll() is None:
                    process.terminate();process.wait(timeout=15)
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('executable',type=Path);p.add_argument('report',type=Path);a=p.parse_args()
    result=run(a.executable.resolve());a.report.write_text(json.dumps(result,indent=2),encoding='utf8');print('API rejected 21 unauthorized probes; real native cancellation preserved data; port released.')
