"""Accept only real native-window/UIA evidence, independently of CDP or QA codes."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import threading
import time

import psutil
from pywinauto import Desktop
from qa_packaged_windows import launch
from native_windows_evidence import environment, windows_for_pids, lifecycle_records, cdp_probe, capture_owned_window, port_released
from native_dialogs import prompt_field


def wait_for(work,seconds=20):
    deadline=time.monotonic()+seconds
    while time.monotonic()<deadline:
        value=work()
        if value:return value
        time.sleep(.2)
    raise TimeoutError('Native acceptance condition not observed')


def named(root,title,types=('Button','Hyperlink','Text')):
    for item in root.descendants():
        if item.element_info.name==title and item.element_info.control_type in types:
            return item
    return None


def invoke(root,title):
    item=wait_for(lambda:named(root,title,('Button','Hyperlink')))
    try:item.iface_scroll_item.ScrollIntoView()
    except Exception:pass
    item.invoke()


def run(executable,bundle,out,run_id,head_commit):
    # Fixed identifiers make a timeout actionable without logging exception text.
    run.action='read_build_info'
    facts=json.loads((bundle/'build-info.json').read_text(encoding='utf-8-sig'))
    run.action='verify_archive_hash'
    archive=bundle/facts['archive']
    assert hashlib.file_digest(archive.open('rb'),'sha256').hexdigest()==facts['archive_sha256']
    run.action='verify_extracted_payload'
    for item in facts['files']:
        file=executable.parent/item['path']
        assert file.is_relative_to(executable.parent) and '..' not in Path(item['path']).parts
        with file.open('rb') as stream:assert hashlib.file_digest(stream,'sha256').hexdigest()==item['sha256']
    report={'source_commit':facts['source_commit'],'pr_head_commit':head_commit,'build_run_id':str(run_id),
            'archive_sha256':facts['archive_sha256'],'executable_sha256':facts['executable_sha256'],
            'method':'native-uia','result':'failed','environment':environment(),
            'stages':{'executable':False,'native_window':False,'native_authorization':False,'qa_native_connection':False},
            'native_cancel_preserved':False,'natural_shutdown':False,'port_released':False}
    process=None;port=None;root=None;data=None;owned=set();main_hwnd=None
    try:
        with tempfile.TemporaryDirectory(prefix='ritmo-native-',ignore_cleanup_errors=True) as folder:
            home=Path(folder);data=home/'Ritmo';data.mkdir();(data/'.migration_disabled').write_text('1')
            config=json.loads((Path(__file__).resolve().parents[1]/'config/config.json').read_text(encoding='utf8'))
            config['tutor']['model_root']=str(home/'no-models');(data/'config.json').write_text(json.dumps(config),encoding='utf8')
            try:
                # No launcher pipe is granted here. This window must authorize itself.
                report['action']='launch_wait_backend'
                process,port=launch(executable,home,grant_qa=False)
                report['stages']['executable']=True
                report['cdp']=cdp_probe(process.qa_debug_port)
                owned={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]}
                def main_window():
                    matches=[w for w in windows_for_pids({process.pid}) if w['title']=='Ritmo · estudo pessoal' and w['visible']]
                    return matches[0] if matches else None
                report['action']='wait_visible_native_window'
                window=wait_for(main_window,40);main_hwnd=window['hwnd'];report['native_window']=window
                report['stages']['native_window']=True
                report['initial_screenshot']=capture_owned_window(main_hwnd,out/'native-window-initial.png')
                root=Desktop(backend='uia').window(handle=main_hwnd).wrapper_object()
                controls=root.descendants()
                report['native_control_types']={kind:sum(c.element_info.control_type==kind for c in controls) for kind in ('Button','Edit','Hyperlink','Document','Pane')}
                report['native_label_presence']={label:any(c.element_info.name==label for c in controls) for label in ('Criar matéria','Meu plano','Configurações','Autorizar esta janela')}
                report['action']='connect_uia_document'
                wait_for(lambda:named(root,'Criar matéria',('Button',)),30)
                report['stages']['qa_native_connection']=True
                # A real native UI action must write the synthetic subject through
                # its own authorized renderer. An API/browser test cannot set this.
                report['action']='create_subject_through_native_ui'
                invoke(root,'Meu plano')
                field=wait_for(lambda:named(root,'Nova matéria',('Edit',)))
                field.set_edit_text('QA nativa isolada')
                invoke(root,'Adicionar matéria')
                def subject_written():
                    with sqlite3.connect(data/'ritmo.db',timeout=2) as db:
                        return db.execute('SELECT COUNT(*) FROM subjects WHERE name=?',('QA nativa isolada',)).fetchone()[0]==1
                report['action']='verify_authorized_native_write'
                wait_for(subject_written)
                report['stages']['native_authorization']=True
                report['native_write_verified']=True
                report['action']='open_native_settings'
                invoke(root,'Configurações')
                report['screenshot']=capture_owned_window(main_hwnd,out/'native-window.png')
                # Invoke asynchronously: native script dialogs may hold the UIA call.
                action=threading.Thread(target=lambda:invoke(root,'Apagar dados do aplicativo'),daemon=True);action.start()
                user=ctypes.windll.user32;user.FindWindowW.restype=ctypes.c_void_p;user.GetDlgItem.restype=ctypes.c_void_p
                native_title='Ritmo · apagar dados pessoais'
                for _ in range(3):
                    def modal():
                        handle=user.FindWindowW(None,native_title)
                        if handle:
                            pid=ctypes.c_ulong();user.GetWindowThreadProcessId(ctypes.c_void_p(handle),ctypes.byref(pid))
                            if pid.value==process.pid:return ('native',int(handle),None)
                        # WebView2 can expose script dialogs inside its existing
                        # UIA tree instead of creating a top-level HWND.
                        if named(root,'OK',('Button',)):
                            return ('script',main_hwnd,root)
                        # Default WebView2 JavaScript confirm/prompt dialogs belong
                        # to this process tree. Never inspect other desktop windows.
                        live_owned={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]}
                        for w in windows_for_pids(live_owned):
                            if w['hwnd']==main_hwnd or not w['visible']:continue
                            dialog=Desktop(backend='uia').window(handle=w['hwnd']).wrapper_object()
                            ok=named(dialog,'OK',('Button',))
                            if ok:return ('script',w['hwnd'],dialog)
                        return None
                    report['action']='erase_confirmation_dialog'
                    report['dialog_step']=_
                    kind,handle,dialog=wait_for(modal,20)
                    if kind=='native':
                        report['action']='cancel_native_erase'
                        no=user.GetDlgItem(ctypes.c_void_p(handle),7);assert no
                        # UIA Invoke works without relying on BM_CLICK activation
                        # of a background dialog. The selected HWND is IDNO only.
                        Desktop(backend='uia').window(handle=int(no)).wrapper_object().invoke()
                        wait_for(lambda:not user.IsWindow(ctypes.c_void_p(handle)))
                        break
                    ok=wait_for(lambda:named(dialog,'OK',('Button',)))
                    if _==1:
                        # Embedded script dialogs can expose background form
                        # fields too. Never select the first Edit on the page.
                        allowed={process.pid,*[p.pid for p in psutil.Process(process.pid).children(recursive=True)]}
                        field=wait_for(lambda:prompt_field(ok,allowed))
                        field.iface_value.SetValue('APAGAR')
                    elif _!=0:
                        raise RuntimeError('Unexpected script dialog before native confirmation')
                    wait_for(lambda:named(dialog,'OK',('Button',))).invoke()
                else:raise RuntimeError('Native erase confirmation did not appear')
                action.join(timeout=5)
                report['action']='verify_cancel_preserved_data'
                assert process.poll() is None and subject_written()
                wait_for(lambda:named(root,'Apagar dados do aplicativo',('Button',)))
                report['native_cancel_preserved']=True
                report['screenshot_after_cancel']=capture_owned_window(main_hwnd,out/'native-after-cancel.png')
                # The native close button/path, never the HTTP quit endpoint.
                report['action']='close_native_window'
                user.PostMessageW(ctypes.c_void_p(main_hwnd),0x0010,0,0)
                assert process.wait(timeout=30)==0
                report['natural_shutdown']=True;report['port_released']=port_released(port)
                assert report['port_released']
                assert report['environment']['window_station_visible'] and report['environment']['input_desktop_open']
                report['result']='passed';report['action']='completed'
            finally:
                report['lifecycle']=lifecycle_records(data/'ritmo.log')
                if process:
                    report['windows_at_end']=windows_for_pids({process.pid}) if process.poll() is None else []
                if process and process.poll() is None:
                    process.terminate();process.wait(timeout=15)
                    report['forced_cleanup']=True
    except Exception as error:
        report['error_type']=type(error).__name__
    finally:
        (out/'native-ui.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf8')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('executable',type=Path);parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--run-id',required=True);parser.add_argument('--head-commit',required=True)
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=False)
    try:
        result=run(args.executable.resolve(),args.bundle.resolve(),args.output.resolve(),args.run_id,args.head_commit)
    except Exception as error:
        result={'result':'failed','error_type':type(error).__name__,'phase':'preflight','action':getattr(run,'action','read_arguments'),
                'build_run_id':args.run_id,'pr_head_commit':args.head_commit,
                'stages':{'executable':False,'native_window':False,'native_authorization':False,'qa_native_connection':False}}
        (args.output/'native-ui.json').write_text(json.dumps(result,indent=2),encoding='utf8')
    print(json.dumps({'result':result['result'],'stages':result['stages'],'error_type':result.get('error_type')}))
    raise SystemExit(0 if result['result']=='passed' else 1)
