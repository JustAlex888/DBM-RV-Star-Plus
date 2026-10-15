"""Phase 8 UAT revision: verified sources -> complete staged tree -> reversible install.

The frozen engine remains the exact-block transformation implementation. This
module changes delivery policy only; it never adapts unknown source content.
"""
from __future__ import annotations

import os
import re
import shutil
import stat
import time
import zipfile
from pathlib import Path

from engine import dbm_rv_phase8_engine as core

ENGINE_VERSION = '1.3.3-phase8-uat-fix'
core.ENGINE_VERSION = ENGINE_VERSION  # session/result identity of this composed engine
CONTENT_MODEL_SHA256 = 'a949ee5d60bcb8e2df94b245382a872aaa846f44a0435df7b7514c93f8f9218c'


def long_path(path):
    path = Path(path).absolute()
    text = str(path)
    if os.name == 'nt' and not text.startswith('\\\\?\\'):
        return Path('\\\\?\\UNC\\' + text[2:] if text.startswith('\\\\') else '\\\\?\\' + text)
    return path


def safe_chain(path: Path) -> None:
    path = long_path(path)
    for item in (path, *path.parents):
        if core.is_reparse(item):
            raise core.UnsafePathFailure('REPARSE_PATH_REJECTED', str(item))


def normalized_dirs(files, explicit=()):
    result = set(explicit)
    for name in files:
        result.update(p.as_posix() for p in core.safe_relative_path(name).parents if p.as_posix() != '.')
    return result


class PatchEngine(core.PatchEngine):
    def __init__(self, backup_path=None, expected_inventory=None, expected_mode=None, progress=None, **kwargs):
        super().__init__(**kwargs)
        self.progress = progress
        self.existing_roots = []
        self.expected_inventory = expected_inventory
        self.expected_mode = expected_mode
        self.mode = None
        self.roots = []
        self.expected = {}
        self.before = {}
        self.preserved_files = {}
        self.preserved_files_verified = False
        self.displaced = []
        self.installed = []
        self.source_container_hashes = {}
        self.lock_path = None
        stamp = time.strftime('%Y%m%d-%H%M%S')
        self.backup_root = self.target_root.parent / 'DBM-RV-Patcher-Backup' / f'{stamp}-{self.session_id}'
        if backup_path is not None:
            approved = long_path(backup_path)
            if approved.parent != long_path(self.backup_root.parent) or not re.fullmatch(r'\d{8}-\d{6}-[a-f0-9]{12}', approved.name):
                raise core.UnsafePathFailure('BACKUP_PATH_POLICY_MISMATCH', str(approved))
            self.backup_root = approved

    def _new_session(self):
        safe_chain(self.target_root)
        safe_chain(self.session_parent)
        wow = self.target_root.parent.parent.resolve()
        try:
            self.session_parent.resolve().relative_to(wow)
        except ValueError:
            pass
        else:
            raise core.UnsafePathFailure('SESSION_DIRECTORY_INSIDE_WOW_ROOT', str(self.session_parent))
        super()._new_session()

    def _set_state(self, state):
        super()._set_state(state)
        if self.progress:
            self.progress({'state': state, 'mode': self.mode, 'root_count': len(self.existing_roots),
                           'ignored_file_count': len(self.preserved_files)})

    def _classify_family_entry(self, item):
        """No-follow object type FIRST: a link is never treated as its referent."""
        info = os.lstat(item)
        if stat.S_ISLNK(info.st_mode) or getattr(info, 'st_file_attributes', 0) & getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400):
            raise core.UnsafePathFailure('DBM_REPARSE_ROOT_REJECTED', str(item))
        safe_chain(item.parent)
        if stat.S_ISDIR(info.st_mode):
            core.safe_relative_path(item.name)
            return 'DIRECTORY'
        if stat.S_ISREG(info.st_mode):
            if item.name.casefold() in {name.casefold() for name in self.roots}:
                raise core.UnsafePathFailure('DBM_TARGET_ROOT_BLOCKED_BY_FILE', str(item))
            return 'PRESERVED_REGULAR_FILE'
        raise core.UnsafePathFailure('DBM_SPECIAL_ROOT_REJECTED', str(item))

    def _family_inventory(self, base):
        base = long_path(base)
        safe_chain(base)
        roots, files = [], {}
        if base.exists():
            for item in base.iterdir():
                if not item.name.casefold().startswith('dbm-'):
                    continue
                kind = self._classify_family_entry(item)
                if kind == 'DIRECTORY':
                    roots.append(item.name)
                else:
                    files[item.name] = core.sha256_file(item)
        return sorted(roots, key=str.casefold), dict(sorted(files.items(), key=lambda pair: pair[0].casefold()))

    def _family_roots(self, base):
        return self._family_inventory(base)[0]

    def _verify_preserved_files(self, reason, failure_class):
        actual = self._family_inventory(self.target_root)[1]
        if actual != self.preserved_files:
            name = next(name for name in sorted(set(actual) | set(self.preserved_files))
                        if actual.get(name) != self.preserved_files.get(name))
            raise failure_class(reason, str(self.target_root / name))

    def _snapshot(self, base):
        """Complete root/entity inventory, including empty directories, no traversal links."""
        base = long_path(base)
        result = {}
        safe_chain(base)
        for name in self._family_roots(base):
            root = base / name
            if not root.exists() and not root.is_symlink():
                continue
            safe_chain(root)
            if not root.is_dir():
                raise core.UnsafePathFailure('MANAGED_ROOT_NOT_DIRECTORY', str(root))
            result[name + '/'] = 'DIR'
            for current, dirs, files in os.walk(root, followlinks=False):
                for item in dirs + files:
                    p = Path(current) / item
                    safe_chain(p)
                    raw = p.relative_to(base).as_posix()
                    core.safe_relative_path(raw)
                    if p.is_dir():
                        result[raw + '/'] = 'DIR'
                    elif p.is_file():
                        if p.stat().st_nlink != 1:
                            raise core.UnsafePathFailure('HARDLINK_REJECTED', str(p))
                        result[raw] = core.sha256_file(p)
                    else:
                        raise core.UnsafePathFailure('UNSAFE_ENTITY', str(p))
        return result

    def _validate_inputs(self):
        if not self.target_root.is_dir():
            raise core.BaselineFailure('TARGET_ROOT_MISSING', str(self.target_root))
        safe_chain(self.target_root)
        self.manifest = core.load_pinned_json(self.manifest_path, core.MANIFEST_SHA256, 'MANIFEST')
        self.baseline = core.load_pinned_json(self.baseline_model_path, core.BASELINE_MODEL_SHA256, 'BASELINE_MODEL')
        self.records = self.manifest['records']
        self.record_paths = core.validate_record_paths(self.records)
        if len(self.records) != core.EXPECTED_RECORDS:
            raise core.BaselineFailure('MANIFEST_RECORD_COUNT_MISMATCH')
        profile = self.baseline['verification_profiles']['EXTRACTED_ADDONS_TREE_STRICT']
        self.clean = {e['path']: e['sha256'] for e in profile['file_manifest']}
        self.expected = dict(self.clean)
        self.expected.update({r['target_relative_path']: r['result_file_sha256'] for r in self.records})
        # Target remains pinned; replacement ownership is explicitly ALL DBM-*.
        self.roots = sorted(set(profile['managed_roots']) | {p.parts[0] for p in self.record_paths})
        for name in self.roots:
            if len(core.safe_relative_path(name).parts) != 1:
                raise core.UnsafePathFailure('INVALID_ROOT_ALLOWLIST', name)
        for record in self.records:
            if record['operation_type'] == 'ADD_PROJECT_FILE':
                self._read_payload_file(self.project_payload_root, record, 'PROJECT_PAYLOAD')
        model = core.load_pinned_json(self.manifest_path.parent / 'SOURCE_CONTENT_MODEL.json', CONTENT_MODEL_SHA256, 'SOURCE_CONTENT_MODEL')
        for key, path in self.source_paths.items():
            safe_chain(path)
            if not path.is_file():
                raise core.BaselineFailure(f'SOURCE_{key}_MISSING', str(path))
            actual_sha = core.sha256_file(path)
            self.source_container_hashes[key] = actual_sha
            if key == 'S08' and actual_sha != core.SOURCE_SHA256[key]:
                raise core.BaselineFailure('SOURCE_S08_SHA_MISMATCH', actual_sha)
            try:
                archive = zipfile.ZipFile(path)
                self.source_zips[key] = archive
                members = self._validate_zip_member_names(archive)
                explicit_dirs = []
                folded = set()
                for info in archive.infolist():
                    name = info.filename.rstrip('/')
                    rel = core.safe_relative_path(name)
                    if any(':' in p or p.endswith((' ', '.')) for p in rel.parts):
                        raise core.BaselineFailure('SOURCE_ARCHIVE_UNSAFE_NAME', name)
                    mode = info.external_attr >> 16
                    if stat.S_ISLNK(mode):
                        raise core.BaselineFailure('SOURCE_ARCHIVE_UNSAFE_ENTITY', name)
                    if name.casefold() in folded:
                        raise core.BaselineFailure('SOURCE_ARCHIVE_PATH_COLLISION', name)
                    folded.add(name.casefold())
                    if info.is_dir():
                        explicit_dirs.append(name)
                expected = model[key]['files']
                canonical_prefix = next(iter(expected)).split('/')[0]
                actual_prefixes = {name.split('/')[0] for name in members}
                allowed_prefixes = {canonical_prefix}
                if key == 'S01':
                    allowed_prefixes.add('DBM-RV-LEG-e97f138de7d3ba846e8a2ee36a35730831e04e27')
                if len(actual_prefixes) != 1 or not actual_prefixes <= allowed_prefixes:
                    raise core.BaselineFailure(f'SOURCE_{key}_ROOT_MISMATCH')
                actual_prefix = next(iter(actual_prefixes))
                def normalize(name):
                    return canonical_prefix + name[len(actual_prefix):]
                # The pinned saved S01 container uses DBM-RV-LEG-main; exact
                # GitHub commit downloads use DBM-RV-LEG-<commit>. Only that
                # immutable wrapper-name difference is normalized, not contents.
                members = {normalize(name): info for name, info in members.items()}
                explicit_dirs = [normalize(name) for name in explicit_dirs]
                if set(members) != set(expected):
                    raise core.BaselineFailure(f'SOURCE_{key}_CONTENT_PATH_MISMATCH')
                if normalized_dirs(members, explicit_dirs) != normalized_dirs(expected, model[key]['directories']):
                    raise core.BaselineFailure(f'SOURCE_{key}_LAYOUT_MISMATCH')
                for name, sha in expected.items():
                    if core.sha256_bytes(archive.read(members[name])) != sha:
                        raise core.BaselineFailure(f'SOURCE_{key}_CONTENT_HASH_MISMATCH', name)
                self.source_members[key] = members
            except (OSError, zipfile.BadZipFile, RuntimeError) as exc:
                raise core.BaselineFailure(f'SOURCE_{key}_ARCHIVE_MALFORMED', str(exc)) from exc
        # Validate every record's source dependency before staging.
        for record in self.records:
            key = record.get('source_id')
            if key in self.source_zips:
                identity = record['source_identity']
                self._read_source_member(key, identity['source_relative_path'], identity['source_file_sha256'])
        self.before = self._snapshot(self.target_root)
        self.existing_roots, self.preserved_files = self._family_inventory(self.target_root)
        files = {k: v for k, v in self.before.items() if not k.endswith('/')}
        expected_dirs = {p + '/': 'DIR' for p in normalized_dirs(self.expected)}
        if self.before == (self.expected | expected_dirs):
            self.mode = 'ALREADY_PATCHED'
            self.already_patched = True
            self.managed_output_digest_sha256 = core.EXPECTED_MANAGED_OUTPUT_DIGEST_SHA256
            self._set_state('ALREADY_PATCHED')
        elif not self.before:
            self.mode = 'FRESH_INSTALL'
        elif self.before == (self.clean | {p + '/': 'DIR' for p in normalized_dirs(self.clean)}):
            self.mode = 'CLEAN_BASELINE'
        else:
            self.mode = 'REPLACE_EXISTING_DBM'
        self.inventory_digest = core.aggregate_digest(self.before | self.preserved_files)
        if ((self.expected_inventory is not None and self.inventory_digest != self.expected_inventory)
                or (self.expected_mode is not None and self.mode != self.expected_mode)):
            raise core.BaselineFailure('TARGET_CHANGED_SINCE_USER_CHECK')
        self.logger.emit('PRECHECK_ALL', mode=self.mode, explicit_roots=self.roots, existing_roots=self.existing_roots,
                         ignored_regular_files=[str(self.target_root / name) for name in self.preserved_files],
                         preserved_regular_file_sha256=self.preserved_files,
                         source_container_sha256=self.source_container_hashes,
                         backup_root=str(self.backup_root))
        self._set_state('INPUTS_VERIFIED')

    def _verify_baseline(self):
        # Existing content is classified, never used as a transformation donor.
        self._set_state(self.mode)

    def _build_staging(self):
        self._set_state('BUILDING_CLEAN_BASE')
        source_prefix = next(iter(self.source_members['S01'])).split('/')[0]
        for name, sha in self.clean.items():
            data = self._read_source_member('S01', source_prefix + '/' + name, sha)
            destination = self.staging_root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
        self._set_state('CLEAN_BASE_BUILT')
        self._set_state('APPLYING_PROJECT_TRANSFORMATIONS')
        # Exact 119 transformations are inherited unchanged from the frozen core.
        super()._build_staging()

    def _verify_staging(self):
        actual = {k: v for k, v in self._snapshot(self.staging_root).items() if not k.endswith('/')}
        if actual != self.expected:
            raise core.StagingFailure('FULL_STAGING_TREE_MISMATCH')
        for record in self.records:
            if (self.staging_root / record['target_relative_path']).stat().st_size != record['result_size_bytes']:
                raise core.StagingFailure('STAGED_SIZE_MISMATCH', record['target_relative_path'])
        self._set_state('STAGING_VERIFIED')

    def _recheck_preconditions(self):
        if self.fault.target_changed_after_staging:
            raise core.BaselineFailure('INJECTED_TARGET_CHANGED_BEFORE_COMMIT')
        for key, path in self.source_paths.items():
            safe_chain(path)
            if core.sha256_file(path) != self.source_container_hashes[key]:
                raise core.BaselineFailure('SOURCE_CHANGED_BEFORE_COMMIT', key)
        if self._snapshot(self.target_root) != self.before:
            raise core.BaselineFailure('TARGET_CHANGED_BEFORE_COMMIT')
        self._verify_preserved_files('PRESERVED_DBM_FILE_CHANGED_BEFORE_COMMIT', core.BaselineFailure)
        self._verify_staging()
        self._set_state('PRECOMMIT_RECHECKED')

    def _backup(self):
        if not self.before:
            self._set_state('BACKUP_NOT_REQUIRED')
            return
        self._set_state('BACKUP_IN_PROGRESS')
        safe_chain(self.backup_root)
        backup = long_path(self.backup_root)
        backup.mkdir(parents=True, exist_ok=False)
        for name in self.existing_roots:
            source = self.target_root / name
            if source.exists():
                shutil.copytree(long_path(source), backup / name, copy_function=shutil.copy2)
        if self.fault.backup_failure:
            raise core.BackupFailure('INJECTED_BACKUP_FAILURE')
        self._set_state('BACKUP_COPIED')
        if self._family_roots(self.backup_root) != self.existing_roots or self._snapshot(self.backup_root) != self.before:
            raise core.BackupFailure('FULL_BACKUP_TREE_MISMATCH')
        if self._snapshot(self.target_root) != self.before:
            raise core.BackupFailure('TARGET_CHANGED_DURING_BACKUP')
        self._verify_preserved_files('PRESERVED_DBM_FILE_CHANGED_DURING_BACKUP', core.BackupFailure)
        self.backup_manifest = [{'relative_path': p, 'pre_state': 'FILE', 'sha256': sha}
                                for p, sha in self.before.items() if not p.endswith('/')]
        core.write_json(backup / 'BACKUP_MANIFEST.json', {
            'engine_version': ENGINE_VERSION, 'target_root': str(self.target_root),
            'roots': self.existing_roots, 'entities': self.before, 'status': 'BACKUP_VERIFIED'})
        self._set_state('BACKUP_VERIFIED')

    def _commit(self):
        # Repeat both checks immediately before displacing any managed root.
        self._recheck_preconditions()
        if self.before and self._snapshot(self.backup_root) != self.before:
            raise core.BackupFailure('BACKUP_CHANGED_BEFORE_COMMIT')
        self.commit_started = True
        self._set_state('COMMIT_IN_PROGRESS')
        for name in self.existing_roots:
            current = self.target_root / name
            if current.exists():
                # Same-volume rename into verified backup keeps the last exact old
                # tree, even if a concurrent writer changed it during the rename.
                displaced_root = long_path(self.backup_root) / '_displaced'
                displaced_root.mkdir(exist_ok=True)
                safe_chain(current)
                os.rename(long_path(current), displaced_root / name)
                self.displaced.append(name)
                self.target_write_count += 1
        if self.displaced and self._snapshot(self.backup_root / '_displaced') != self.before:
            raise core.ApplyFailure('TARGET_CHANGED_DURING_DISPLACEMENT')
        if self._family_roots(self.target_root):
            raise core.ApplyFailure('DBM_ROOTS_REMAIN_AFTER_DISPLACEMENT')
        self._set_state('OLD_DBM_DISPLACED')
        if self.fault.mid_commit_after is not None:
            raise core.ApplyFailure('INJECTED_AFTER_DISPLACEMENT_FAILURE')
        self._set_state('INSTALLING_CLEAN_TARGET')
        for name in self.roots:
            destination = self.target_root / name
            if destination.exists():
                raise core.ApplyFailure('TARGET_ROOT_APPEARED_DURING_COMMIT', str(destination))
            self.installed.append(name)
            shutil.copytree(long_path(self.staging_root / name), long_path(destination), copy_function=shutil.copy2)
            self.commit_write_count += sum(1 for p in (self.staging_root / name).rglob('*') if p.is_file())
            self.target_write_count += 1
        if self.fault.post_commit_corruption:
            first = self.target_root / next(iter(self.expected))
            first.write_bytes(b'INJECTED_CORRUPTION')
        self._set_state('COMMIT_COMPLETE')

    def _verify_commit(self):
        self._set_state('VERIFYING_COMPLETE_TARGET')
        actual = self._snapshot(self.target_root)
        if actual != (self.expected | {p + '/': 'DIR' for p in normalized_dirs(self.expected)}):
            raise core.VerifyFailure('FULL_COMMIT_TREE_MISMATCH')
        self._verify_preserved_files('PRESERVED_DBM_FILE_CHANGED_AFTER_COMMIT', core.VerifyFailure)
        self.preserved_files_verified = True
        self.logger.emit('PRESERVED_REGULAR_FILES_VERIFIED', files=self.preserved_files,
                         count=len(self.preserved_files))
        super()._verify_commit()

    def _rollback(self):
        self._set_state('ROLLBACK_IN_PROGRESS')
        try:
            for name in reversed(self.installed):
                target = self.target_root / name
                safe_chain(target)
                if target.exists():
                    shutil.rmtree(long_path(target))
            # Restore every displaced root by rename, retaining files outside the
            # 119 overlay and empty directories. Undisplaced roots stay intact.
            for name in reversed(self.displaced):
                target = self.target_root / name
                if target.exists():
                    raise RuntimeError('Concurrent target blocks rollback: ' + str(target))
                os.rename(long_path(self.backup_root) / '_displaced' / name, long_path(target))
            if self._snapshot(self.target_root) != self.before:
                raise RuntimeError('Full original tree restoration mismatch')
            # Managed-tree recovery does not authorize repairing an external file.
            try:
                self._verify_preserved_files('PRESERVED_DBM_FILE_CHANGED_AFTER_ROLLBACK', core.VerifyFailure)
                self.preserved_files_verified = True
            except core.EngineFailure as exc:
                self.logger.emit('PRESERVED_REGULAR_FILES_NOT_RESTORED', reason_code=exc.reason, detail=exc.detail)
            self._set_state('ROLLBACK_VERIFIED')
            return 'ROLLBACK_VERIFIED'
        except Exception as exc:
            self.logger.emit('ROLLBACK_FAILED', detail=str(exc), backup_root=str(self.backup_root))
            self.state = 'ROLLBACK_FAILED'
            return self.state

    def run(self):
        # Local per-target lock prevents cooperating patcher sessions overlapping;
        # independent filesystem changes are handled by exact tree rechecks.
        safe_chain(self.target_root)
        safe_chain(self.session_parent)
        self.session_parent.mkdir(parents=True, exist_ok=True)
        key = core.sha256_bytes(str(self.target_root.resolve()).casefold().encode())[:24]
        lock = self.session_parent / (key + '.lock')
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        try:
            result = super().run()
            result.details.update({'mode': self.mode, 'backup_planned_path': str(self.backup_root) if self.before and not self.already_patched else None,
                                   'existing_roots': self.existing_roots,
                                   'ignored_regular_files': [str(self.target_root / name) for name in self.preserved_files],
                                   'preserved_regular_file_sha256': self.preserved_files,
                                   'preserved_regular_files_verified': self.preserved_files_verified or result.outcome in ('READY', 'ALREADY_PATCHED'),
                                   'managed_roots': self.roots, 'full_output_file_count': len(self.expected),
                                   'full_output_digest_sha256': core.aggregate_digest(self.expected),
                                   'source_container_sha256': self.source_container_hashes,
                                   'inventory_digest_sha256': getattr(self, 'inventory_digest', None),
                                   'source_verification': 'FULL_CONTENT_AND_LAYOUT_PINNED'})
            if self.backup_root.exists():
                result.backup_root = self.backup_root
            core.write_json(result.session_dir / 'summary.json', result.as_dict() | {'engine_version': ENGINE_VERSION})
            return result
        finally:
            os.close(descriptor)
            lock.unlink()
