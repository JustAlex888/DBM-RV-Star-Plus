#!/usr/bin/env python3
"""Fail-closed Windows x64 frozen-executable packaging gate.

Checks are intentionally independent of DBM content packs. Nothing here runs the
EXE or writes a real WoW folder. It verifies the static Windows PE/manifest and
packaging tree; interactive GUI/transaction/UAT remain separate tests.
"""
from __future__ import annotations

import argparse
import ctypes
import hashlib
import json
import os
import stat
import struct
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BAD_COMPONENTS = {
    "project_payload",
    "source_content_model.json",
    "baseline_verification_model_0.1.7_test_phase7.json",
    "canonical_transformation_manifest_0.1.7_test_phase7.json",
}
RT_MANIFEST = 24
LOAD_LIBRARY_AS_DATAFILE = 0x00000002

class ValidationError(RuntimeError):
    """A static release gate failed; do not distribute the binary."""


def digest_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as inp:
        for chunk in iter(lambda: inp.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_pe_header(path: Path) -> dict:
    """Read PE architecture from bytes without importing or executing the file."""
    with path.open("rb") as f:
        start = f.read(64)
        if len(start) < 64 or start[:2] != b"MZ":
            raise ValidationError("PE_DOS_HEADER_INVALID")
        pointer = struct.unpack_from("<I", start, 0x3C)[0]
        if pointer < 64 or pointer > path.stat().st_size - 24:
            raise ValidationError("PE_NT_OFFSET_INVALID")
        f.seek(pointer)
        hdr = f.read(26)
    if len(hdr) != 26 or hdr[:4] != b"PE\x00\x00":
        raise ValidationError("PE_NT_SIGNATURE_INVALID")
    machine = struct.unpack_from("<H", hdr, 4)[0]
    optional_size = struct.unpack_from("<H", hdr, 20)[0]
    characteristics = struct.unpack_from("<H", hdr, 22)[0]
    opt_magic = struct.unpack_from("<H", hdr, 24)[0]
    if machine != 0x8664 or opt_magic != 0x20B:
        raise ValidationError(f"PE_NOT_AMD64_PE32PLUS machine=0x{machine:04x} magic=0x{opt_magic:04x}")
    if optional_size < 2 or not (characteristics & 0x0002):
        raise ValidationError("PE_NOT_EXECUTABLE_IMAGE")
    return {"pe_machine": "AMD64", "pe_optional_header": "PE32+", "exe_image": True}


def read_embedded_manifest(exe_path: Path) -> bytes:
    """Read RT_MANIFEST with Win32 APIs as data: LoadLibraryEx does not execute EXE."""
    if sys.platform != "win32":
        raise ValidationError("MANIFEST_RESOURCE_CHECK_REQUIRES_WINDOWS")
    from ctypes import wintypes

    dll = ctypes.WinDLL("kernel32", use_last_error=True)
    dll.LoadLibraryExW.argtypes = [wintypes.LPCWSTR, wintypes.HANDLE, wintypes.DWORD]
    dll.LoadLibraryExW.restype = wintypes.HMODULE
    dll.FindResourceW.argtypes = [wintypes.HMODULE, wintypes.LPCWSTR, wintypes.LPCWSTR]
    dll.FindResourceW.restype = wintypes.HRSRC
    dll.SizeofResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
    dll.SizeofResource.restype = wintypes.DWORD
    dll.LoadResource.argtypes = [wintypes.HMODULE, wintypes.HRSRC]
    dll.LoadResource.restype = wintypes.HGLOBAL
    dll.LockResource.argtypes = [wintypes.HGLOBAL]
    dll.LockResource.restype = ctypes.c_void_p
    dll.FreeLibrary.argtypes = [wintypes.HMODULE]
    dll.FreeLibrary.restype = wintypes.BOOL

    module = dll.LoadLibraryExW(str(exe_path), None, LOAD_LIBRARY_AS_DATAFILE)
    if not module:
        raise ValidationError(f"PE_RESOURCE_OPEN_FAILED {ctypes.get_last_error()}")
    try:
        # PyInstaller commonly embeds #1, but do not assume one ID across versions.
        for resource_id in (1, 2, 3):
            rs = dll.FindResourceW(module, ctypes.cast(ctypes.c_void_p(resource_id), wintypes.LPCWSTR),
                                   ctypes.cast(ctypes.c_void_p(RT_MANIFEST), wintypes.LPCWSTR))
            if not rs:
                continue
            size = dll.SizeofResource(module, rs)
            if not (0 < size < 1024 * 1024):
                raise ValidationError("PE_MANIFEST_RESOURCE_SIZE_INVALID")
            handle = dll.LoadResource(module, rs)
            data_pointer = dll.LockResource(handle) if handle else None
            if not data_pointer:
                raise ValidationError("PE_MANIFEST_RESOURCE_READ_FAILED")
            return ctypes.string_at(data_pointer, size)
    finally:
        dll.FreeLibrary(module)
    raise ValidationError("PE_MANIFEST_RESOURCE_MISSING")


def assert_asinvoker(manifest: bytes) -> None:
    try:
        root = ET.fromstring(manifest)
    except ET.ParseError as e:
        raise ValidationError(f"PE_MANIFEST_INVALID_XML: {e}") from e
    nodes = [node for node in root.iter() if node.tag.rsplit("}", 1)[-1] == "requestedExecutionLevel"]
    if len(nodes) != 1 or nodes[0].attrib.get("level") != "asInvoker" or nodes[0].attrib.get("uiAccess") != "false":
        raise ValidationError("PE_MANIFEST_NOT_ASINVOKER")


def safe_file_tree(dist: Path) -> tuple[int, str]:
    """Disallow links/reparse nodes, version-frozen payloads, extra executable roots."""
    if dist.is_symlink() or not dist.is_dir():
        raise ValidationError("DIST_NOT_REAL_DIRECTORY")
    internal = dist / "_internal"
    if internal.is_symlink() or not internal.is_dir():
        raise ValidationError("ONEDIR_INTERNAL_MISSING")
    entries = []
    for current, dirs, files in os.walk(dist, followlinks=False):
        for name in dirs + files:
            path = Path(current) / name
            relative = path.relative_to(dist)
            if any(x.casefold() in BAD_COMPONENTS for x in relative.parts):
                raise ValidationError(f"FROZEN_DBM_RESOURCE_PRESENT: {relative.as_posix()}")
            mode = path.lstat()
            if stat.S_ISLNK(mode.st_mode) or getattr(mode, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400):
                raise ValidationError(f"DISTRIBUTION_REPARSE_OBJECT: {relative.as_posix()}")
            if path.is_file():
                if not stat.S_ISREG(mode.st_mode):
                    raise ValidationError(f"DISTRIBUTION_SPECIAL_OBJECT: {relative.as_posix()}")
                entries.append(f"{relative.as_posix()}\x00{digest_file(path)}")
            elif not path.is_dir():
                raise ValidationError(f"DISTRIBUTION_UNKNOWN_OBJECT: {relative.as_posix()}")
    if not any(item.startswith("_internal/") for item in entries):
        raise ValidationError("ONEDIR_INTERNAL_EMPTY")
    return len(entries), hashlib.sha256("\n".join(sorted(entries)).encode()).hexdigest()


def verify(dist: Path, *, manifest_reader=read_embedded_manifest) -> dict:
    exe = dist / "DBM-RV-Patcher.exe"
    if not exe.is_file() or exe.is_symlink():
        raise ValidationError("FROZEN_EXE_MISSING")
    pe = read_pe_header(exe)
    assert_asinvoker(manifest_reader(exe))
    count, tree_sha = safe_file_tree(dist)
    return {"status": "STATIC_VERIFIED_BINARY_STRUCTURE_ONLY", "exe": exe.name,
            "exe_size": exe.stat().st_size, "exe_sha256": digest_file(exe),
            "distribution_file_count": count, "distribution_tree_digest_sha256": tree_sha,
            "manifest_execution_level": "asInvoker", "manifest_ui_access": False,
            "format": "ONEDIR", "version_specific_dbm_assets_embedded": False,
            "game_status": "NOT_OBSERVED", "human_windows_uat": "NOT_OBSERVED", **pe}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Win x64 PE, asInvoker and onedir static gate")
    parser.add_argument("--dist", type=Path, default=ROOT / "dist" / "DBM-RV-Patcher")
    parser.add_argument("--report", type=Path, default=ROOT / "build" / "reports" / "WINDOWS_BINARY_GATE.json")
    args = parser.parse_args(argv)
    try:
        report = verify(args.dist)
    except (ValidationError, OSError, ValueError) as exc:
        print(f"STATIC_FAILED: {exc}", file=sys.stderr)
        return 1
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print("STATIC_VERIFIED_BINARY_STRUCTURE_ONLY", report["exe_sha256"], "files", report["distribution_file_count"])
    print("Static report:", args.report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
