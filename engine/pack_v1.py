"""Strict data-only pack_v1 verifier.  No imported/executed code from update ZIP.

The archive is an *input*, not a trust anchor. For public distribution users
must independently verify the published SHA-256/signature of the complete pack.
"""
from __future__ import annotations

import hashlib
import base64
import json
import os
import re
import stat
import zipfile
from pathlib import Path
from typing import Any

from engine import dbm_rv_phase8_engine as core

PACK_SCHEMA = 'dbm-rv-star-plus/pack_v1'
INSTALLER_API = 1
MAX_PACK_BYTES = 64 * 1024 * 1024
MAX_MEMBER_BYTES = 8 * 1024 * 1024
MAX_JSON_BYTES = 8 * 1024 * 1024
MAX_ENTRIES = 1800
HEX64 = re.compile(r'^[a-f0-9]{64}$')
ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.+-]{0,95}$')
META_FILES = ('manifests/transformations.json', 'manifests/source_gates.json', 'manifests/target.json')
CODE_EXTENSIONS = ('.py', '.pyc', '.pyd', '.ps1', '.bat', '.cmd', '.exe', '.dll', '.so', '.sh', '.js', '.vbs')
# Windows Win32 filename rules apply even when validating on Linux. Without
# these guards a data-only pack could pass Linux tests but create device-name,
# wildcard or invalid-path errors on the user's Windows machine.
WIN32_FORBIDDEN = frozenset('<>:"\\|?*')
WIN32_DEVICE = re.compile(r'^(?:CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[1-9¹²³]|LPT[1-9¹²³]) *(?:\..*)?$', re.IGNORECASE)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def require(condition: bool, code: str, detail: str = '') -> None:
    if not condition:
        raise core.BaselineFailure(code, detail)


def relpath(raw: str) -> str:
    require(isinstance(raw, str), 'PACK_UNSAFE_PATH', repr(raw))
    require('\\' not in raw and '\x00' not in raw and ':' not in raw and not raw.startswith('/'), 'PACK_UNSAFE_PATH', raw)
    require(all(part not in ('.', '..', '') and not part.endswith((' ', '.')) for part in raw.split('/')), 'PACK_UNSAFE_PATH', raw)
    require(not any(ord(ch) < 32 for ch in raw), 'PACK_UNSAFE_PATH', raw)
    require(not any(ch in WIN32_FORBIDDEN for ch in raw), 'PACK_WINDOWS_FORBIDDEN_CHAR', raw)
    require(not any(WIN32_DEVICE.fullmatch(part) for part in raw.split('/')), 'PACK_WINDOWS_DEVICE_NAME', raw)
    parts = core.safe_relative_path(raw).parts
    require('/'.join(parts) == raw, 'PACK_UNSAFE_PATH', raw)
    return raw


def dbm_path(raw: str) -> str:
    raw = relpath(raw)
    require(raw.startswith('DBM-') and '/' in raw, 'PACK_PATH_OUTSIDE_DBM', raw)
    require(raw.split('/')[0].casefold().startswith('dbm-'), 'PACK_PATH_OUTSIDE_DBM', raw)
    return raw


def hash64(value: Any, reason: str) -> str:
    require(isinstance(value, str) and bool(HEX64.fullmatch(value)), reason)
    return value


def positive_int(value: Any, code: str, maximum: int = MAX_PACK_BYTES) -> int:
    require(type(value) is int and 0 <= value <= maximum, code)
    return value


class VerifiedPack:
    def __init__(self, path: Path):
        self.path = Path(path).absolute()
        require(self.path.is_file(), 'PACK_NOT_FOUND', str(self.path))
        require(not core.is_reparse(self.path), 'PACK_REPARSE_REJECTED', str(self.path))
        require(self.path.stat().st_size <= MAX_PACK_BYTES, 'PACK_OVERSIZED')
        self.sha256 = core.sha256_file(self.path)
        try:
            with zipfile.ZipFile(self.path) as archive:
                self._inspect_zip(archive)
                self.pack = self._read_json(archive, 'pack.json', MAX_JSON_BYTES)
                self._validate_metadata(archive)
                self.transforms = self._read_json(archive, META_FILES[0], MAX_JSON_BYTES)
                self.gates = self._read_json(archive, META_FILES[1], MAX_JSON_BYTES)
                self.target = self._read_json(archive, META_FILES[2], MAX_JSON_BYTES)
                self._validate_models(archive)
        except (OSError, ValueError, KeyError, TypeError, zipfile.BadZipFile, UnicodeError) as exc:
            if isinstance(exc, core.EngineFailure):
                raise
            raise core.BaselineFailure('PACK_MALFORMED', str(exc)) from exc

    def _inspect_zip(self, archive: zipfile.ZipFile) -> None:
        require(len(archive.infolist()) <= MAX_ENTRIES, 'PACK_TOO_MANY_MEMBERS')
        total, folded, members = 0, set(), {}
        for info in archive.infolist():
            name = info.filename
            require(not info.is_dir(), 'PACK_DIRECTORY_ENTRY_FORBIDDEN', name)
            relpath(name)
            require(name.casefold() not in folded, 'PACK_CASE_COLLISION', name)
            folded.add(name.casefold())
            require(not (info.flag_bits & 0x1), 'PACK_ENCRYPTION_FORBIDDEN', name)
            require(info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED), 'PACK_COMPRESSION_UNSUPPORTED', name)
            mode = info.external_attr >> 16
            require(not stat.S_ISLNK(mode) and not (mode & 0o170000 and not stat.S_ISREG(mode)), 'PACK_SPECIAL_ENTITY_REJECTED', name)
            require(0 <= info.file_size <= MAX_MEMBER_BYTES, 'PACK_MEMBER_OVERSIZED', name)
            total += info.file_size
            require(total <= MAX_PACK_BYTES, 'PACK_TOTAL_OVERSIZED')
            require(info.compress_size > 0 or info.file_size == 0, 'PACK_COMPRESSION_INVALID', name)
            require(info.file_size <= max(4096, info.compress_size * 150), 'PACK_COMPRESSION_RATIO_REJECTED', name)
            suffix = Path(name).suffix.casefold()
            require(suffix not in CODE_EXTENSIONS, 'PACK_EXECUTABLE_MEMBER_REJECTED', name)
            allow = name == 'pack.json' or name in META_FILES or name.startswith('payload/DBM-') or name.startswith('licenses/')
            require(allow, 'PACK_MEMBER_NOT_ALLOWED', name)
            if name.startswith('payload/'):
                dbm_path(name[len('payload/'):])
            if name.startswith('licenses/'):
                require(suffix in ('.txt', '.md'), 'PACK_LICENSE_TYPE_NOT_ALLOWED', name)
            members[name] = info
        require('pack.json' in members and all(k in members for k in META_FILES), 'PACK_REQUIRED_METADATA_MISSING')
        require(archive.testzip() is None, 'PACK_CRC_FAILED')
        self.members = members

    @staticmethod
    def _read_json(archive: zipfile.ZipFile, name: str, limit: int) -> dict[str, Any]:
        data = archive.read(name)
        require(len(data) <= limit, 'PACK_JSON_TOO_LARGE', name)
        value = json.loads(data.decode('utf-8'))
        require(type(value) is dict, 'PACK_JSON_OBJECT_EXPECTED', name)
        return value

    def _validate_metadata(self, archive: zipfile.ZipFile) -> None:
        p = self.pack
        require(p.get('schema') == PACK_SCHEMA, 'PACK_SCHEMA_INCOMPATIBLE')
        require(p.get('engine_api') == INSTALLER_API, 'PACK_ENGINE_API_INCOMPATIBLE')
        require(p.get('product') == 'DBM-RV-Star-Plus', 'PACK_PRODUCT_MISMATCH')
        require(bool(re.fullmatch(r'[0-9]+(?:\.[0-9]+){2}(?:[-A-Za-z0-9_.]*)?', str(p.get('version', '')))), 'PACK_VERSION_INVALID')
        for field in ('build_id', 'provenance'):
            require(isinstance(p.get(field), str) and bool(ID.fullmatch(p[field])), 'PACK_IDENTITY_INVALID', field)
        require(isinstance(p.get('description'), str) and len(p['description']) <= 256, 'PACK_DESCRIPTION_INVALID')
        hashes = p.get('content_hashes')
        require(isinstance(hashes, dict) and set(hashes) == set(META_FILES), 'PACK_CONTENT_HASH_MANIFEST_INVALID')
        for name in META_FILES:
            require(digest(archive.read(name)) == hash64(hashes[name], 'PACK_META_HASH_INVALID'), 'PACK_META_HASH_MISMATCH', name)
        entry_hashes = p.get('payload_hashes')
        require(type(entry_hashes) is dict, 'PACK_PAYLOAD_MAP_INVALID')
        require(set(entry_hashes) == {k for k in self.members if k.startswith(('payload/', 'licenses/'))}, 'PACK_UNDECLARED_PAYLOAD_MEMBER')
        for name, entry in entry_hashes.items():
            relpath(name)
            require(isinstance(entry, dict), 'PACK_PAYLOAD_ENTRY_INVALID', name)
            require(digest(archive.read(name)) == hash64(entry.get('sha256'), 'PACK_PAYLOAD_HASH_INVALID'), 'PACK_PAYLOAD_HASH_MISMATCH', name)
            require(len(archive.read(name)) == positive_int(entry.get('size'), 'PACK_PAYLOAD_SIZE_INVALID', MAX_MEMBER_BYTES), 'PACK_PAYLOAD_SIZE_MISMATCH', name)

    def _validate_models(self, archive: zipfile.ZipFile) -> None:
        require(self.transforms.get('schema') == 'dbm-rv/transformations-v1', 'PACK_TRANSFORM_SCHEMA_INVALID')
        require(self.gates.get('schema') == 'dbm-rv/source-gates-v1', 'PACK_SOURCE_SCHEMA_INVALID')
        require(self.target.get('schema') == 'dbm-rv/target-v1', 'PACK_TARGET_SCHEMA_INVALID')
        rows = self.target.get('files')
        roots = self.target.get('managed_roots')
        require(type(rows) is list and 0 < len(rows) <= 1600, 'PACK_TARGET_FILES_INVALID')
        require(type(roots) is list and 0 < len(roots) <= 100, 'PACK_TARGET_ROOTS_INVALID')
        require(all(type(r) is str and re.fullmatch(r'DBM-[A-Za-z0-9+_-]+', r) for r in roots), 'PACK_TARGET_ROOTS_INVALID')
        require(len(set(x.casefold() for x in roots)) == len(roots), 'PACK_ROOT_CASE_COLLISION')
        target_files, folded = {}, set()
        for row in rows:
            require(type(row) is dict, 'PACK_TARGET_ROW_INVALID')
            path = dbm_path(row.get('path'))
            require(path.casefold() not in folded, 'PACK_TARGET_CASE_COLLISION', path)
            folded.add(path.casefold())
            target_files[path] = {'sha256': hash64(row.get('sha256'), 'PACK_TARGET_SHA_INVALID'), 'size': positive_int(row.get('size'), 'PACK_TARGET_SIZE_INVALID', MAX_MEMBER_BYTES)}
        require({x.split('/')[0] for x in target_files} == set(roots), 'PACK_ROOTS_MISMATCH')
        digest_expected = hash64(self.target.get('tree_digest_sha256'), 'PACK_TREE_HASH_INVALID')
        require(core.aggregate_digest({k: v['sha256'] for k,v in target_files.items()}) == digest_expected, 'PACK_TREE_HASH_MISMATCH')
        self.files = target_files
        self.roots = sorted(roots)
        sources = self.gates.get('sources')
        require(type(sources) is list and 1 <= len(sources) <= 8, 'PACK_SOURCE_GATES_INVALID')
        self.sources = {}
        for group in sources:
            require(type(group) is dict, 'PACK_SOURCE_GATE_INVALID')
            sid = group.get('id')
            require(isinstance(sid, str) and bool(re.fullmatch(r'S[0-9]{2}', sid)) and sid not in self.sources, 'PACK_SOURCE_ID_INVALID')
            require(group.get('role') in ('UPSTREAM', 'DONOR'), 'PACK_SOURCE_ROLE_INVALID', sid)
            require(bool(group.get('provenance')), 'PACK_SOURCE_PROVENANCE_MISSING', sid)
            roots_allowed = group.get('archive_roots')
            require(isinstance(roots_allowed, list) and len(roots_allowed) in (1,2), 'PACK_SOURCE_ROOTS_INVALID', sid)
            require(all(isinstance(r, str) and (r == '__DIRECT__' or bool(ID.fullmatch(r))) for r in roots_allowed), 'PACK_SOURCE_ROOTS_INVALID', sid)
            sha_allow = group.get('archive_sha256_allowlist')
            require(isinstance(sha_allow, list) and 1 <= len(sha_allow) <= 3, 'PACK_SOURCE_CONTAINER_HASHES_INVALID', sid)
            for h in sha_allow:hash64(h,'PACK_SOURCE_CONTAINER_HASH_INVALID')
            members = group.get('files')
            require(type(members) is dict and len(members) >= 1 and len(members) <= 2000, 'PACK_SOURCE_FILE_MAP_INVALID', sid)
            for name,h in members.items():
                dbm_path(name)
                hash64(h, 'PACK_SOURCE_MEMBER_HASH_INVALID')
            require(len({k.casefold() for k in members}) == len(members), 'PACK_SOURCE_CASE_COLLISION', sid)
            self.sources[sid] = group
        records = self.transforms.get('records')
        require(type(records) is list and len(records) == len(target_files), 'PACK_RECORD_COUNT_MISMATCH')
        self.records = records
        folded = set()
        used_payload = set()
        for record in records:
            require(type(record) is dict, 'PACK_RECORD_INVALID')
            path = dbm_path(record.get('target_relative_path'))
            require(path in target_files, 'PACK_RECORD_UNKNOWN_TARGET', path)
            require(path.casefold() not in folded, 'PACK_RECORD_DUPLICATE', path)
            folded.add(path.casefold())
            require(record.get('result_file_sha256') == target_files[path]['sha256'], 'PACK_RECORD_TARGET_SHA_MISMATCH', path)
            require(record.get('result_size_bytes') == target_files[path]['size'], 'PACK_RECORD_TARGET_SIZE_MISMATCH', path)
            typ = record.get('operation_type')
            require(typ in ('COPY_VERIFIED_SOURCE_FILE', 'PATCH_VERIFIED_SOURCE_FILE', 'ADD_PROJECT_FILE'), 'PACK_OPERATION_UNSUPPORTED', str(typ))
            if typ == 'ADD_PROJECT_FILE':
                member = 'payload/' + path
                require(record.get('payload_relative_path') == path, 'PACK_PAYLOAD_TARGET_MISMATCH', path)
                require(member in self.members, 'PACK_PAYLOAD_MISSING', member)
                require(self.pack['payload_hashes'][member]['sha256'] == record['result_file_sha256'], 'PACK_PAYLOAD_TARGET_SHA_MISMATCH', path)
                used_payload.add(member)
                require(not record.get('source_id') and not record.get('operations'), 'PACK_PROJECT_RECORD_EXTRA_FIELDS', path)
            else:
                sid = record.get('source_id')
                require(sid in self.sources, 'PACK_UNKNOWN_SOURCE', path)
                name = dbm_path(record.get('source_relative_path'))
                require(name in self.sources[sid]['files'], 'PACK_SOURCE_MEMBER_UNPINNED', path)
                require(record.get('source_file_sha256') == self.sources[sid]['files'][name], 'PACK_SOURCE_MEMBER_SHA_MISMATCH', path)
                operations = record.get('operations', [])
                if typ == 'COPY_VERIFIED_SOURCE_FILE':
                    require(not operations and record['result_file_sha256'] == record['source_file_sha256'], 'PACK_COPY_SHA_MISMATCH', path)
                else:
                    require(type(operations) is list and 1 <= len(operations) <= 900, 'PACK_PATCH_OPERATIONS_INVALID', path)
                    require(hash64(record.get('baseline_file_sha256'), 'PACK_BASELINE_SHA_INVALID') == record['source_file_sha256'], 'PACK_BASELINE_SHA_MISMATCH', path)
                    for op in operations:
                        require(type(op) is dict, 'PACK_PATCH_OPERATION_INVALID', path)
                        kind = op.get('operation_type')
                        require(kind in ('REPLACE_EXACT_BLOCK', 'REPLACE_EXACT_SPAN'), 'PACK_PATCH_OPERATION_UNSUPPORTED', path)
                        if kind == 'REPLACE_EXACT_SPAN':
                            positive_int(op.get('offset_bytes'), 'PACK_SPAN_OFFSET_INVALID', MAX_MEMBER_BYTES)
                            positive_int(op.get('remove_length'), 'PACK_SPAN_REMOVE_LENGTH_INVALID', MAX_MEMBER_BYTES)
                            hash64(op.get('remove_sha256'), 'PACK_SPAN_REMOVED_SHA_INVALID')
                            encoded = op.get('replacement_b64')
                            require(type(encoded) is str and len(encoded) <= MAX_MEMBER_BYTES * 2, 'PACK_SPAN_BASE64_INVALID', path)
                            try:
                                replacement = base64.b64decode(encoded, validate=True)
                            except ValueError as exc:
                                raise core.BaselineFailure('PACK_SPAN_BASE64_INVALID', path) from exc
                            require(digest(replacement) == hash64(op.get('replacement_sha256'), 'PACK_SPAN_REPLACEMENT_SHA_INVALID'), 'PACK_SPAN_REPLACEMENT_SHA_MISMATCH', path)
                        else:
                            require(op.get('expected_occurrence_count') == 1, 'PACK_PATCH_OCCURRENCES_INVALID', path)
                            for rawkey, hashkey in [('match_text','match_sha256'), ('replacement_text','replacement_sha256')]:
                                value = op.get(rawkey)
                                require(isinstance(value, str) and value != '' and len(value.encode('utf8')) < MAX_MEMBER_BYTES, 'PACK_PATCH_TEXT_INVALID', path)
                                require(digest(value.encode('utf8')) == hash64(op.get(hashkey), 'PACK_PATCH_HASH_INVALID'), 'PACK_PATCH_TEXT_HASH_MISMATCH', path)
        require(used_payload == {k for k in self.members if k.startswith('payload/')}, 'PACK_UNUSED_PAYLOAD_FILE')

    def payload_bytes(self, path: str) -> bytes:
        with zipfile.ZipFile(self.path) as archive:
            return archive.read('payload/' + dbm_path(path))

    def identity(self) -> dict[str, Any]:
        return {k: self.pack[k] for k in ('product', 'version', 'build_id', 'provenance')} | {'pack_sha256': self.sha256,
            'roots': len(self.roots), 'files': len(self.files), 'tree_digest_sha256': self.target['tree_digest_sha256']}
