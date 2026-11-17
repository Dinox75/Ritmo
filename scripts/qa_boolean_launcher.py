"""Start and close ONLY a newly spawned sandbox; never control existing apps."""
import argparse,hashlib,json,socket,subprocess,sys,time,urllib.request,uuid
from pathlib import Path


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    root=(a.output/('owned-'+uuid.uuid4().hex)).resolve();root.mkdir()
    assert root.is_relative_to(a.output.resolve())
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    script=Path(__file__).with_name('open_boolean_lesson.py')
    command=[sys.executable,str(script),'--run',str(root),'--port',str(port),'--no-browser']
    with (root/'stderr.txt').open('w') as err:
        child=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=err,text=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        code=child.stdout.readline().strip().removeprefix('RITMO_AUTH_CODE ')
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));base=f'http://127.0.0.1:{port}'
        for _ in range(100):
            try:
                with opener.open(base+'/api/app/status',timeout=1) as response:info=json.load(response)
                break
            except OSError:time.sleep(.1)
        else:raise RuntimeError('Novo sandbox não abriu; logs em '+str(root))
        assert info['instance_id']==hashlib.sha256(str(root/'ritmo.db').encode()).hexdigest()
        assert child.poll() is None
        second=subprocess.run(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=15,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        assert second.returncode==0 and child.poll() is None
        with opener.open(urllib.request.Request(base+'/api/session',data=json.dumps({'code':code}).encode(),headers={'Content-Type':'application/json'})) as response:cookie=response.headers['Set-Cookie'].split(';')[0]
        # Endpoint belongs to the process and random directory created above.
        with opener.open(urllib.request.Request(base+'/api/app/quit',data=b'{}',headers={'Content-Type':'application/json','Cookie':cookie}),timeout=5) as response:assert json.load(response)['closing']
        assert child.wait(timeout=20)==0
    with socket.socket() as sock:assert sock.connect_ex(('127.0.0.1',port))!=0
    result={'owned_sandbox':str(root),'opened':True,'second_click_reused':True,'quit_exit_code':0,'port_released':True,'existing_processes_touched':False}
    (a.output/'qa.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result))


if __name__=='__main__':main()
