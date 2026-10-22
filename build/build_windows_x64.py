#!/usr/bin/env python3
"""One Windows x64-only onedir builder for ALL compatible external pack_v1 ZIPs.

No version-dependent DBM manifest/payload is frozen. Never use this script to
build a mislabeled Linux binary. Post-build PE64/asInvoker verification is gated.
"""
from __future__ import annotations

import ctypes
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def windows_amd64_gate() -> None:
    if sys.platform != "win32":
        raise SystemExit("BLOCKED_DEPENDENCY: build only on Windows x64 (not Linux/macOS)")
    if struct.calcsize("P") != 8:
        raise SystemExit("BLOCKED_DEPENDENCY: Python interpreter is not 64-bit")
    # Windows PROCESSOR_ARCHITECTURE is not authoritative for emulated platforms;
    # GetNativeSystemInfo provides the native processor's architecture.
    class SYSTEM_INFO(ctypes.Structure):
        _fields_ = [("wProcessorArchitecture", ctypes.c_ushort), ("wReserved", ctypes.c_ushort),
                    ("dwPageSize", ctypes.c_ulong), ("lpMinimumApplicationAddress", ctypes.c_void_p),
                    ("lpMaximumApplicationAddress", ctypes.c_void_p), ("dwActiveProcessorMask", ctypes.c_size_t),
                    ("dwNumberOfProcessors", ctypes.c_ulong), ("dwProcessorType", ctypes.c_ulong),
                    ("dwAllocationGranularity", ctypes.c_ulong), ("wProcessorLevel", ctypes.c_ushort),
                    ("wProcessorRevision", ctypes.c_ushort)]
    info = SYSTEM_INFO()
    ctypes.windll.kernel32.GetNativeSystemInfo(ctypes.byref(info))
    if info.wProcessorArchitecture != 9:  # PROCESSOR_ARCHITECTURE_AMD64
        raise SystemExit("BLOCKED_DEPENDENCY: Windows native system is not AMD64")


def main() -> None:
    windows_amd64_gate()  # BEFORE import PyInstaller, before build output writes
    sys.path.insert(0, str(ROOT))
    from PyInstaller.__main__ import run

    run([
        "--noconfirm", "--clean", "--onedir", "--windowed", "--name", "DBM-RV-Patcher",
        "--distpath", str(ROOT / "dist"),
        "--workpath", str(ROOT / "build" / "work"),
        "--specpath", str(ROOT / "build"),
        "--paths", str(ROOT),
        "--manifest", str(ROOT / "build" / "windows_asinvoker.manifest"),
        "--version-file", str(ROOT / "build" / "windows_version_info.txt"),
        "--icon", str(ROOT / "assets" / "patcher-legion.ico"),
        "--add-data", str(ROOT / "assets") + ";resources/assets",
        "--collect-data", "customtkinter",
        '--add-data', str(ROOT / 'recipes') + ';recipe_code',
        '--hidden-import', 'runpy', '--hidden-import', 'difflib', '--hidden-import', 'ast',
        '--hidden-import', 'csv', '--hidden-import', 'collections',
        str(ROOT / "wrapper" / "installer_ui.py"),
    ])
    from build.verify_windows_binary import main as verify_main
    result = verify_main(["--dist", str(ROOT / "dist" / "DBM-RV-Patcher")])
    if result != 0:
        raise SystemExit("STATIC_FAILED: PyInstaller output failed the Windows PE/manifest gate")


if __name__ == "__main__":
    main()
