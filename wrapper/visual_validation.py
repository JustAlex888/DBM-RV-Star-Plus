import ctypes
from ctypes import wintypes as w
from PIL import Image
from pathlib import Path
def capture(hwnd,path):
    u=ctypes.WinDLL('user32',use_last_error=True);g=ctypes.WinDLL('gdi32',use_last_error=True)
    u.GetWindowDC.argtypes=[w.HWND];u.GetWindowDC.restype=w.HDC
    u.PrintWindow.argtypes=[w.HWND,w.HDC,w.UINT];u.PrintWindow.restype=w.BOOL
    u.GetWindowRect.argtypes=[w.HWND,ctypes.POINTER(w.RECT)]
    u.ReleaseDC.argtypes=[w.HWND,w.HDC]
    g.CreateCompatibleDC.argtypes=[w.HDC];g.CreateCompatibleDC.restype=w.HDC
    g.CreateCompatibleBitmap.argtypes=[w.HDC,ctypes.c_int,ctypes.c_int];g.CreateCompatibleBitmap.restype=w.HBITMAP
    g.SelectObject.argtypes=[w.HDC,w.HGDIOBJ];g.SelectObject.restype=w.HGDIOBJ
    g.DeleteObject.argtypes=[w.HGDIOBJ];g.DeleteDC.argtypes=[w.HDC]
    class BI(ctypes.Structure):
        _fields_=[('size',w.DWORD),('width',w.LONG),('height',w.LONG),('planes',w.WORD),('bpp',w.WORD),('compression',w.DWORD),('image',w.DWORD),('x',w.LONG),('y',w.LONG),('used',w.DWORD),('important',w.DWORD)]
    g.GetDIBits.argtypes=[w.HDC,w.HBITMAP,w.UINT,w.UINT,ctypes.c_void_p,ctypes.POINTER(BI),w.UINT]
    rect=w.RECT();u.GetWindowRect(hwnd,ctypes.byref(rect));width=rect.right-rect.left;height=rect.bottom-rect.top
    dc=u.GetWindowDC(hwnd);mem=g.CreateCompatibleDC(dc);bmp=g.CreateCompatibleBitmap(dc,width,height);prior=g.SelectObject(mem,bmp)
    try:
        assert u.PrintWindow(hwnd,mem,2)
        bi=BI(ctypes.sizeof(BI),width,-height,1,32,0,0,0,0,0,0);buf=ctypes.create_string_buffer(width*height*4)
        assert g.GetDIBits(mem,bmp,0,height,buf,ctypes.byref(bi),0)
        Image.frombuffer('RGB',(width,height),buf.raw,'raw','BGRX',0,1).save(path)
    finally:g.SelectObject(mem,prior);g.DeleteObject(bmp);g.DeleteDC(mem);u.ReleaseDC(hwnd,dc)

def capture_own_window(root,path):
    hwnd=ctypes.windll.user32.GetParent(root.winfo_id()) or root.winfo_id()
    u=ctypes.windll.user32
    u.SetThreadDpiAwarenessContext.argtypes=[ctypes.c_void_p]
    u.SetThreadDpiAwarenessContext.restype=ctypes.c_void_p
    previous=u.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
    try:
        p=Path(path);p.parent.mkdir(parents=True,exist_ok=True);capture(hwnd,p)
    finally:u.SetThreadDpiAwarenessContext(previous)
