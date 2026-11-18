"""Launch isolated opt-in Ritmo Boolean lesson, without sensors or personal data."""
import argparse
import hashlib
import json
import logging
import sys
import urllib.request
import webbrowser
import threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from storage.database import Database
from dashboard.app import make_server
from utils.config import DEFAULT_CONFIG,save_config


def validate_sandbox(root):
    root=Path(root).resolve();marker=root/'instance.json'
    if (root/'ritmo.db').exists():
        if not marker.is_file():raise ValueError('Banco existente sem identificação de sandbox; escolha uma pasta nova. Nenhum dado foi alterado.')
        metadata=json.loads(marker.read_text(encoding='utf8'))
        if Path(metadata.get('database','')).resolve()!=root/'ritmo.db':raise ValueError('Identificação da instância não corresponde ao banco; preservado.')


def main():
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);p.add_argument('--port',type=int,default=8770);p.add_argument('--no-browser',action='store_true');a=p.parse_args()
    root=a.run.resolve();repo=Path(__file__).resolve().parents[1]
    if root.is_relative_to(repo):raise ValueError('Use uma pasta isolada fora do repositório.')
    validate_sandbox(root)
    root.mkdir(parents=True,exist_ok=True)
    logging.basicConfig(filename=root/'launcher.log',level=logging.INFO)
    # A second click may reopen ONLY this same isolated database.
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(f'http://127.0.0.1:{a.port}/api/app/status',timeout=1) as r: info=json.load(r)
        marker=root/'instance.json'
        if not marker.exists() or json.loads(marker.read_text())['port']!=a.port or info.get('instance_id')!=hashlib.sha256(str(root/'ritmo.db').encode()).hexdigest():
            raise ValueError('Porta já ocupada; nenhum outro aplicativo foi encerrado. Escolha outra porta.')
        if not a.no_browser:webbrowser.open(f'http://127.0.0.1:{a.port}/boolean-lesson.html')
        return
    except OSError:pass
    config_path=root/'config.json'
    if not config_path.exists():
        config=json.loads(DEFAULT_CONFIG.read_text(encoding='utf8'))
        for sensor in ('window_tracker','presence_detector','idle_tracker'):config[sensor]['enabled']=False
        config['multitask_analyzer']={'enabled':False};config['experiments']={'boolean_lesson':True}
        save_config(config,config_path)
    db=Database(root/'ritmo.db');db.initialize();server=make_server(db,a.port,config_path=config_path)
    (root/'instance.json').write_text(json.dumps({'port':server.server_port,'database':str(db.path)}),encoding='utf8')
    code=server.session.issue_code()
    thread=threading.Thread(target=server.serve_forever);thread.start()
    if sys.stdout:print('RITMO_AUTH_CODE '+code,flush=True)
    if not a.no_browser:
        webbrowser.open(f'http://127.0.0.1:{server.server_port}/authorize.html')
        if sys.stdout is None:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,'Código de autorização (5 min, uso único):\n'+code+'\n\nCopie para a página aberta. Ctrl+C copia este diálogo.','Ritmo · autorizar aula isolada',0x40)
    try:thread.join()
    finally:server.shutdown();server.server_close();server.tutor_runtime.stop()


if __name__=='__main__':
    try:main()
    except Exception as error:
        if sys.platform=='win32' and '--no-browser' not in sys.argv:
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,str(error),'Ritmo · aula isolada',0x10)
        else:raise
