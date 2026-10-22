"""Read-only Windows directory-right checks and an explicit UAC relaunch.

No ACL changes, file probes, automatic APPLY, or execution through a shell.
The elevated process receives only selections, never a trusted CHECK snapshot.
"""
import ctypes
import os
import subprocess
import sys
from pathlib import Path


def is_admin():
    if sys.platform != 'win32':
        return False
    try:
        return bool(ctypes.WinDLL('shell32').IsUserAnAdmin())
    except OSError:
        return False


def directory_right(path, access):
    """Open a directory for specific access without modifying it or its ACL."""
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    create = kernel.CreateFileW
    create.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                       ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    create.restype = wintypes.HANDLE
    close = kernel.CloseHandle
    close.argtypes = [wintypes.HANDLE]
    close.restype = wintypes.BOOL
    handle = create(str(path), access, 7, None, 3, 0x02000000, None)
    if handle == ctypes.c_void_p(-1).value:
        error = ctypes.get_last_error()
        return {'path': str(path), 'access': access, 'status': 'DENIED' if error == 5 else 'UNKNOWN', 'winerror': error}
    close(handle)
    return {'path': str(path), 'access': access, 'status': 'GRANTED'}


def inspect_access(target, roots, backup=None):
    if sys.platform != 'win32':
        return {'status': 'NOT_APPLICABLE', 'checks': [], 'admin': False}
    # Creating the replacement roots needs FILE_ADD_SUBDIRECTORY on AddOns.
    checks = [directory_right(target, 0x0004)]
    # A rename out of AddOns needs DELETE on the source, or DELETE_CHILD on
    # its parent. Either route suffices; requiring both would over-prompt.
    for name in roots:
        item = directory_right(Path(target) / name, 0x10000)
        if item['status'] == 'DENIED':
            parent = directory_right(target, 0x0040)
            if parent['status'] == 'GRANTED':
                item['status'] = 'GRANTED_VIA_PARENT'
        checks.append(item)
    if backup:
        ancestor = Path(backup).parent
        while not ancestor.exists() and ancestor != ancestor.parent:
            ancestor = ancestor.parent
        checks.append(directory_right(ancestor, 0x0004))
    return {'status': 'DENIED' if any(c['status'] == 'DENIED' for c in checks)
            else 'UNKNOWN' if any(c['status'] == 'UNKNOWN' for c in checks) else 'GRANTED',
            'checks': checks, 'admin': is_admin()}


def restart_arguments(values, extra_sources, language):
    # ShellExecute starts at the executable's folder, not necessarily the
    # original working directory. Preserve the meaning of manually typed paths.
    absolute = lambda value: str(Path(value).absolute()) if value else ''
    target, s01, s08, pack = map(absolute, values)
    args = ['--resume-check', '--target', target, '--source-s01', s01,
            '--source-s08', s08, '--pack', pack, '--ui-language', language]
    for sid, path in extra_sources.items():
        if path:
            args.extend(['--source-extra', sid + '=' + absolute(path)])
    return args


def relaunch(args, hwnd=0):
    if sys.platform != 'win32':
        return {'status': 'FAILED', 'winerror': 0}
    executable = str(Path(sys.executable).resolve())
    if not getattr(sys, 'frozen', False):
        args = [str(Path(__file__).with_name('installer_ui.py').resolve()), *args]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    launch = shell.ShellExecuteW
    launch.argtypes = [ctypes.c_void_p, ctypes.c_wchar_p, ctypes.c_wchar_p,
                       ctypes.c_wchar_p, ctypes.c_wchar_p, ctypes.c_int]
    launch.restype = ctypes.c_void_p
    ctypes.set_last_error(0)
    result = launch(hwnd, 'runas', executable, subprocess.list2cmdline(args),
                    str(Path(executable).parent), 1)
    error = ctypes.get_last_error()
    return {'status': 'STARTED' if result and result > 32 else 'CANCELLED' if error == 1223 else 'FAILED',
            'winerror': error, 'shell_code': result or 0}
