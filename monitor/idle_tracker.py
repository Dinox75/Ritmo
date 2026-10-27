"""Ausência de entrada de teclado/mouse; não mede aprendizado."""

import ctypes


def get_idle_time():
    class LASTINPUTINFO(ctypes.Structure):
        _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

    info = LASTINPUTINFO()
    info.cbSize = ctypes.sizeof(info)
    if not ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
        raise OSError("GetLastInputInfo falhou")
    ctypes.windll.kernel32.GetTickCount64.restype = ctypes.c_ulonglong
    tick = ctypes.windll.kernel32.GetTickCount64() & 0xFFFFFFFF
    return ((tick - info.dwTime) & 0xFFFFFFFF) / 1000


def monitorar_inatividade(stop_event, interval, threshold_seconds, emit):
    previous = None
    while not stop_event.is_set():
        idle_seconds = get_idle_time()
        state = "no_input" if idle_seconds >= threshold_seconds else "input_recent"
        if state != previous:
            emit("idle", state, {"idle_seconds": round(idle_seconds, 1),
                                  "threshold_seconds": threshold_seconds})
            previous = state
        stop_event.wait(interval)
