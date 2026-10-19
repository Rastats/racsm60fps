#!/usr/bin/env python3
"""Capture the client area of a process's main window (Windows only).

Fallback for PPSSPP 1.20.4, whose debugger screenshot requests
(gpu.buffer.screenshot / renderColor) answer "Could not download output" on
this machine with both Vulkan and Direct3D 11 (observed 2026-10-19). Uses
PrintWindow with PW_RENDERFULLCONTENT, which also renders DirectX content when
the window is covered by other windows (not when it is minimized). Emulation
keeps running during the capture: use it to look at the screen, not to sample
a frame-exact state (frame-exact output: PPSSPP frame dumps).

Requires Pillow (PIL).
"""
import ctypes
import ctypes.wintypes as wt
from pathlib import Path

user32 = ctypes.WinDLL('user32', use_last_error=True)
gdi32 = ctypes.WinDLL('gdi32', use_last_error=True)

PW_RENDERFULLCONTENT = 0x00000002
DIB_RGB_COLORS = 0
BI_RGB = 0

EnumWindowsProc = ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
user32.EnumWindows.argtypes = [EnumWindowsProc, wt.LPARAM]
user32.GetWindowThreadProcessId.argtypes = [wt.HWND, ctypes.POINTER(wt.DWORD)]
user32.IsWindowVisible.argtypes = [wt.HWND]
user32.GetWindowTextLengthW.argtypes = [wt.HWND]
user32.GetWindow.argtypes = [wt.HWND, wt.UINT]
user32.GetWindow.restype = wt.HWND
user32.GetClientRect.argtypes = [wt.HWND, ctypes.POINTER(wt.RECT)]
user32.GetWindowDC.argtypes = [wt.HWND]
user32.GetWindowDC.restype = wt.HDC
user32.GetDC.argtypes = [wt.HWND]
user32.GetDC.restype = wt.HDC
user32.ReleaseDC.argtypes = [wt.HWND, wt.HDC]
user32.PrintWindow.argtypes = [wt.HWND, wt.HDC, wt.UINT]
user32.IsIconic.argtypes = [wt.HWND]
gdi32.CreateCompatibleDC.argtypes = [wt.HDC]
gdi32.CreateCompatibleDC.restype = wt.HDC
gdi32.CreateCompatibleBitmap.argtypes = [wt.HDC, ctypes.c_int, ctypes.c_int]
gdi32.CreateCompatibleBitmap.restype = wt.HBITMAP
gdi32.SelectObject.argtypes = [wt.HDC, wt.HGDIOBJ]
gdi32.SelectObject.restype = wt.HGDIOBJ
gdi32.DeleteObject.argtypes = [wt.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wt.HDC]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [('biSize', wt.DWORD), ('biWidth', wt.LONG), ('biHeight', wt.LONG),
                ('biPlanes', wt.WORD), ('biBitCount', wt.WORD), ('biCompression', wt.DWORD),
                ('biSizeImage', wt.DWORD), ('biXPelsPerMeter', wt.LONG), ('biYPelsPerMeter', wt.LONG),
                ('biClrUsed', wt.DWORD), ('biClrImportant', wt.DWORD)]


gdi32.GetDIBits.argtypes = [wt.HDC, wt.HBITMAP, wt.UINT, wt.UINT, ctypes.c_void_p,
                            ctypes.POINTER(BITMAPINFOHEADER), wt.UINT]


def main_window(pid):
    """Return the largest visible top-level window owned by `pid` (or None)."""
    found = []

    def cb(hwnd, _):
        owner = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(owner))
        if owner.value == pid and user32.IsWindowVisible(hwnd) and not user32.GetWindow(hwnd, 4):  # GW_OWNER
            r = wt.RECT()
            user32.GetClientRect(hwnd, ctypes.byref(r))
            found.append(((r.right - r.left) * (r.bottom - r.top), hwnd))
        return True

    user32.EnumWindows(EnumWindowsProc(cb), 0)
    return max(found)[1] if found else None


def capture(pid, out_path):
    """Save the client area of the process's main window to a PNG. Returns (path, w, h)."""
    from PIL import Image
    hwnd = main_window(pid)
    if not hwnd:
        raise RuntimeError(f'no visible window for pid {pid}')
    if user32.IsIconic(hwnd):
        raise RuntimeError('window is minimized: PrintWindow cannot render it')
    r = wt.RECT()
    user32.GetClientRect(hwnd, ctypes.byref(r))
    w, h = r.right - r.left, r.bottom - r.top
    hdc_win = user32.GetDC(hwnd)
    hdc_mem = gdi32.CreateCompatibleDC(hdc_win)
    bmp = gdi32.CreateCompatibleBitmap(hdc_win, w, h)
    old = gdi32.SelectObject(hdc_mem, bmp)
    try:
        # PW_CLIENTONLY (1) | PW_RENDERFULLCONTENT (2)
        if not user32.PrintWindow(hwnd, hdc_mem, 0x1 | PW_RENDERFULLCONTENT):
            raise RuntimeError('PrintWindow failed')
        bih = BITMAPINFOHEADER(ctypes.sizeof(BITMAPINFOHEADER), w, -h, 1, 32, BI_RGB, 0, 0, 0, 0, 0)
        buf = ctypes.create_string_buffer(w * h * 4)
        if gdi32.GetDIBits(hdc_mem, bmp, 0, h, buf, ctypes.byref(bih), DIB_RGB_COLORS) != h:
            raise RuntimeError('GetDIBits failed')
        img = Image.frombuffer('RGB', (w, h), buf.raw, 'raw', 'BGRX', 0, 1)
    finally:
        gdi32.SelectObject(hdc_mem, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(hdc_mem)
        user32.ReleaseDC(hwnd, hdc_win)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out, w, h


if __name__ == '__main__':
    import sys
    print(capture(int(sys.argv[1]), sys.argv[2]))
