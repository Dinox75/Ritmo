"""Read-only Win32 evidence for one owned QA process; no desktop-wide screenshots."""
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
import platform
import socket
import struct
import urllib.request
import zlib


def environment():
    user=ctypes.windll.user32;kernel=ctypes.windll.kernel32
    user.GetProcessWindowStation.restype=ctypes.c_void_p
    user.OpenInputDesktop.restype=ctypes.c_void_p
    class Flags(ctypes.Structure):
        _fields_=[('inherit',wintypes.BOOL),('reserved',wintypes.BOOL),('flags',wintypes.DWORD)]
    flags=Flags();needed=wintypes.DWORD();station=user.GetProcessWindowStation()
    readable=bool(user.GetUserObjectInformationW(ctypes.c_void_p(station),1,ctypes.byref(flags),ctypes.sizeof(flags),ctypes.byref(needed)))
    desktop=user.OpenInputDesktop(0,False,0x0100)
    if desktop:user.CloseDesktop(ctypes.c_void_p(desktop))
    session=wintypes.DWORD();kernel.ProcessIdToSessionId(os.getpid(),ctypes.byref(session))
    return {'windows_version':platform.version(),'qa_process_session_id':session.value,
            'window_station_visible':bool(readable and flags.flags&1),'input_desktop_open':bool(desktop)}


def windows_for_pids(pids):
    user=ctypes.windll.user32;found=[]
    @ctypes.WINFUNCTYPE(wintypes.BOOL,wintypes.HWND,wintypes.LPARAM)
    def visit(hwnd,_):
        pid=wintypes.DWORD();user.GetWindowThreadProcessId(hwnd,ctypes.byref(pid))
        if pid.value in pids:
            title=ctypes.create_unicode_buffer(512);kind=ctypes.create_unicode_buffer(256)
            user.GetWindowTextW(hwnd,title,512);user.GetClassNameW(hwnd,kind,256)
            rect=wintypes.RECT();user.GetWindowRect(hwnd,ctypes.byref(rect))
            found.append({'hwnd':int(hwnd),'pid':pid.value,'title':title.value,'class':kind.value,
                          'visible':bool(user.IsWindowVisible(hwnd)),
                          'rect':[rect.left,rect.top,rect.right,rect.bottom]})
        return True
    user.EnumWindows(visit,0)
    return found


def lifecycle_records(path):
    records=[]
    if not path.is_file():return records
    # Export only our allowlisted lifecycle records, never the raw application log.
    keys={'event','phase','state','pid','elapsed_ms','port','surface','error_type','cdp_requested'}
    for line in path.read_text(encoding='utf8',errors='replace').splitlines():
        if 'RITMO_LIFECYCLE ' not in line:continue
        try:
            value=json.loads(line.split('RITMO_LIFECYCLE ',1)[1])
            if value.get('phase') not in {'executable','native','authorization','qa','shutdown'}:continue
            if value.get('state') not in {'started','ready','created','before_show','shown','loaded','requested','authorized','failed','fallback','closing','closed','unavailable','connected'}:continue
            records.append({k:v for k,v in value.items() if k in keys})
        except (ValueError,TypeError):continue
    return records


def cdp_probe(port):
    try:
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(f'http://127.0.0.1:{port}/json/version',timeout=1) as response:
            return {'connected':response.status==200,'status':response.status}
    except Exception as error:return {'connected':False,'error_type':type(error).__name__}


def capture_owned_window(hwnd,path):
    """PrintWindow of the app only. No screen fallback (could capture personal apps)."""
    user=ctypes.windll.user32;gdi=ctypes.windll.gdi32
    user.GetWindowDC.restype=ctypes.c_void_p;gdi.CreateCompatibleDC.restype=ctypes.c_void_p
    gdi.CreateCompatibleBitmap.restype=ctypes.c_void_p;gdi.SelectObject.restype=ctypes.c_void_p
    rect=wintypes.RECT();user.GetWindowRect(ctypes.c_void_p(hwnd),ctypes.byref(rect))
    width,height=rect.right-rect.left,rect.bottom-rect.top
    if not 0<width<=4096 or not 0<height<=4096:return {'captured':False}
    dc=user.GetWindowDC(ctypes.c_void_p(hwnd));memory=gdi.CreateCompatibleDC(ctypes.c_void_p(dc))
    bitmap=gdi.CreateCompatibleBitmap(ctypes.c_void_p(dc),width,height)
    old=gdi.SelectObject(ctypes.c_void_p(memory),ctypes.c_void_p(bitmap))
    try:
        if not user.PrintWindow(ctypes.c_void_p(hwnd),ctypes.c_void_p(memory),2):return {'captured':False}
        gdi.SelectObject(ctypes.c_void_p(memory),ctypes.c_void_p(old))
        class Header(ctypes.Structure):
            _fields_=[('size',wintypes.DWORD),('width',wintypes.LONG),('height',wintypes.LONG),('planes',wintypes.WORD),('bits',wintypes.WORD),('compression',wintypes.DWORD),('image_size',wintypes.DWORD),('x',wintypes.LONG),('y',wintypes.LONG),('colors',wintypes.DWORD),('important',wintypes.DWORD)]
        header=Header();header.size=ctypes.sizeof(Header);header.width=width;header.height=-height;header.planes=1;header.bits=32
        pixels=ctypes.create_string_buffer(width*height*4)
        if not gdi.GetDIBits(ctypes.c_void_p(memory),ctypes.c_void_p(bitmap),0,height,pixels,ctypes.byref(header),0):return {'captured':False}
        raw=pixels.raw;rows=[]
        for y in range(height):
            row=raw[y*width*4:(y+1)*width*4];rgb=bytearray(width*3)
            rgb[0::3]=row[2::4];rgb[1::3]=row[1::4];rgb[2::3]=row[0::4];rows.append(b'\0'+rgb)
        def chunk(name,data):return struct.pack('>I',len(data))+name+data+struct.pack('>I',zlib.crc32(name+data)&0xffffffff)
        png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',width,height,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b'')
        path.write_bytes(png)
        return {'captured':True,'width':width,'height':height,'sha256':hashlib.sha256(png).hexdigest(),'nonuniform_pixels':len(set(raw[::64]))>4}
    finally:
        gdi.SelectObject(ctypes.c_void_p(memory),ctypes.c_void_p(old));gdi.DeleteObject(ctypes.c_void_p(bitmap));gdi.DeleteDC(ctypes.c_void_p(memory));user.ReleaseDC(ctypes.c_void_p(hwnd),ctypes.c_void_p(dc))


def port_released(port):
    with socket.socket() as sock:
        sock.setsockopt(socket.SOL_SOCKET,socket.SO_EXCLUSIVEADDRUSE,1)
        try:sock.bind(('127.0.0.1',port));return True
        except OSError:return False
