"""Private launcher capability; only an inherited OS pipe, never HTTP discovery."""
import ctypes
from utils.lifecycle import event


def write_one_time_code(handle, session):
    if type(handle) is not int or handle<=0:
        raise ValueError('Pipe de autorização inválido')
    kernel=ctypes.windll.kernel32
    pipe=ctypes.c_void_p(handle)
    if kernel.GetFileType(pipe)!=3:
        raise ValueError('A autorização exige um pipe herdado, não um arquivo')
    try:
        payload=(session.issue_code()+'\n').encode('ascii')
        written=ctypes.c_ulong()
        if not kernel.WriteFile(pipe,payload,len(payload),ctypes.byref(written),None) or written.value!=len(payload):
            raise ValueError('Não foi possível entregar a autorização ao lançador')
        event('launcher_pipe_ready','qa','ready')
    finally:
        kernel.CloseHandle(pipe)
