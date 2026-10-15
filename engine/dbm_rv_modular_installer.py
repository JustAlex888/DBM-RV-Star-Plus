"""pack_v1 adapter over the existing 0.1.3 Phase8 full-directory transaction.

Inherits backup/commit/rollback from the previous tested engine. R8 restricts
ownership to manifest roots plus two explicitly retired product roots.
"""
from __future__ import annotations

import os
import stat
import zipfile
from pathlib import Path

from engine import dbm_rv_phase8_engine as core
from engine import dbm_rv_installer as legacy
from engine.pack_v2 import VerifiedPack
from engine.pack_v1 import require, dbm_path

ENGINE_VERSION = '1.5.0-three-source-recipes'
core.ENGINE_VERSION = ENGINE_VERSION
legacy.ENGINE_VERSION = ENGINE_VERSION


class PatchEngine(legacy.PatchEngine):
    RETIRED_PRODUCT_ROOTS = frozenset(('DBM-Uldir', 'DBM-Azeroth-BfA'))
    PROTECTED_DIAGNOSTIC_ROOTS = frozenset(('dbm-rv-freezetrace', 'dbm-rv-testharness'))

    def _independent_tree(self, base, root):
        """Hash preserved directories without following links or admitting writes."""
        result = {root.relative_to(base).as_posix() + '/': 'DIR'}
        for current, dirs, files in os.walk(root, followlinks=False):
            for name in dirs + files:
                p = Path(current) / name
                legacy.safe_chain(p)
                info = os.lstat(p)
                rel = p.relative_to(base).as_posix()
                core.safe_relative_path(rel)
                if stat.S_ISDIR(info.st_mode):
                    result[rel + '/'] = 'DIR'
                elif stat.S_ISREG(info.st_mode) and info.st_nlink == 1:
                    result[rel] = core.sha256_file(p)
                else:
                    raise core.UnsafePathFailure('PRESERVED_ADDON_UNSAFE_ENTITY', str(p))
        return result

    def _family_inventory(self, base):
        """Only manifest roots and two retired product roots can be displaced."""
        base = legacy.long_path(base)
        legacy.safe_chain(base)
        allowed = {r.casefold() for r in self.roots} | {r.casefold() for r in self.RETIRED_PRODUCT_ROOTS}
        roots, preserved = [], {}
        if base.exists():
            for item in base.iterdir():
                if not item.name.casefold().startswith('dbm-'):
                    continue
                kind = self._classify_family_entry(item)
                if kind == 'DIRECTORY' and item.name.casefold() in allowed:
                    roots.append(item.name)
                elif kind == 'DIRECTORY':
                    preserved.update(self._independent_tree(base, item))
                else:
                    preserved[item.name] = core.sha256_file(item)
        return sorted(roots, key=str.casefold), dict(sorted(preserved.items()))

    def __init__(self, *, pack_path: Path, source_selections: dict[str, Path], **kwargs):
        # The old __init__ remains intact; legacy source parameters are inert
        # compatibility placeholders. No embedded manifest or payload is used.
        placeholder = Path(pack_path).absolute()
        super().__init__(manifest_path=placeholder, baseline_model_path=placeholder,
            project_payload_root=placeholder.parent,
            source_s01=Path(source_selections.get('S01', placeholder)),
            source_s08=Path(source_selections.get('S08', placeholder)), **kwargs)
        self.pack_path = placeholder
        self.selection = {k: Path(v).absolute() for k,v in source_selections.items() if v}
        self.bundle = None
        # Use one Windows namespace consistently through inherited transaction
        # checks too, including direct stat() on deeply nested staging files.
        for name in ('target_root','session_parent','session_dir','staging_root','backup_root'):
            setattr(self, name, legacy.long_path(getattr(self, name)))

    def _verify_source_zip(self, sid: str, group: dict, path: Path) -> None:
        legacy.safe_chain(path)
        require(path.is_file(), f'SOURCE_{sid}_MISSING', str(path))
        expected = group['archive_sha256_allowlist']
        actual_sha = core.sha256_file(path)
        require(actual_sha in expected, f'SOURCE_{sid}_SHA_MISMATCH', actual_sha)
        archive = zipfile.ZipFile(path)
        try:
            require(archive.testzip() is None, f'SOURCE_{sid}_CRC_FAILED')
            members, folded = {}, set()
            direct = '__DIRECT__' in group['archive_roots']
            for info in archive.infolist():
                name = info.filename.rstrip('/')
                rel = core.safe_relative_path(name)
                require(not any(':' in p or p.endswith((' ', '.')) for p in rel.parts), f'SOURCE_{sid}_UNSAFE_NAME', name)
                mode = info.external_attr >> 16
                require(not stat.S_ISLNK(mode) and not (mode & 0o170000 and not stat.S_ISREG(mode) and not info.is_dir()), f'SOURCE_{sid}_UNSAFE_ENTITY', name)
                require(name.casefold() not in folded, f'SOURCE_{sid}_CASE_COLLISION', name)
                folded.add(name.casefold())
                if info.is_dir():
                    continue
                if direct:
                    if not name.startswith('DBM-'):
                        continue
                    target = dbm_path(name)
                else:
                    if '/' not in name:
                        continue
                    prefix, target = name.split('/',1)
                    require(prefix in group['archive_roots'], f'SOURCE_{sid}_UNAPPROVED_ROOT', prefix)
                    if not target.startswith('DBM-'):
                        continue
                    target = dbm_path(target)
                require(target not in members, f'SOURCE_{sid}_NORMALIZED_COLLISION', target)
                members[target] = info
            require(set(group['files']) == set(members), f'SOURCE_{sid}_FULL_PATH_SET_MISMATCH')
            for name, sha in group['files'].items():
                require(core.sha256_bytes(archive.read(members[name])) == sha, f'SOURCE_{sid}_MEMBER_HASH_MISMATCH', name)
            self.source_zips[sid] = archive
            self.source_members[sid] = members
            self.source_container_hashes[sid] = actual_sha
        except Exception:
            archive.close()
            raise

    def _validate_inputs(self):
        require(self.target_root.is_dir(), 'TARGET_ROOT_MISSING', str(self.target_root))
        legacy.safe_chain(self.target_root)
        legacy.safe_chain(self.pack_path)
        self.bundle = VerifiedPack(self.pack_path)
        self.records = self.bundle.records
        self.record_paths = core.validate_record_paths(self.records)
        self.expected = {k:v['sha256'] for k,v in self.bundle.files.items()}
        self.roots = list(self.bundle.roots)
        require(not ({r.casefold() for r in self.roots} & self.PROTECTED_DIAGNOSTIC_ROOTS),
                'PACK_CANNOT_MANAGE_INDEPENDENT_DIAGNOSTICS')
        # Each source is pinned by exact ZIP container SHA and complete normalized
        # per-file tree; unknown donor input is NOT auto-guessed.
        for sid, group in self.bundle.sources.items():
            path = self.selection.get(sid)
            require(path is not None, f'SOURCE_{sid}_NOT_SELECTED')
            self._verify_source_zip(sid, group, path)
            self.source_paths[sid] = path
        self.source_paths = {k:self.source_paths[k] for k in self.bundle.sources}
        # Precheck all record source dependencies before any staging/target change.
        self.before = self._snapshot(self.target_root)
        self.existing_roots, self.preserved_files = self._family_inventory(self.target_root)
        expected_dirs = {p+'/':'DIR' for p in legacy.normalized_dirs(self.expected)}
        old_files = {k:v for k,v in self.before.items() if not k.endswith('/')}
        if self.before == (self.expected | expected_dirs):
            self.mode = 'ALREADY_PATCHED'
            self.already_patched = True
            self.managed_output_digest_sha256 = self.bundle.target['tree_digest_sha256']
            self._set_state('ALREADY_PATCHED')
        elif not self.before:
            self.mode = 'FRESH_INSTALL'
        else:
            self.mode = 'REPLACE_EXISTING_DBM'
        self.inventory_digest = core.aggregate_digest(self.before | self.preserved_files)
        if ((self.expected_inventory is not None and self.inventory_digest != self.expected_inventory)
             or (self.expected_mode is not None and self.mode != self.expected_mode)):
            raise core.BaselineFailure('TARGET_CHANGED_SINCE_USER_CHECK')
        self.logger.emit('PRECHECK_ALL', pack=self.bundle.identity(), mode=self.mode,
            explicit_roots=self.roots, existing_roots=self.existing_roots,
            preserved_regular_file_sha256=self.preserved_files,
            source_container_sha256=self.source_container_hashes,
            backup_root=str(self.backup_root))
        self._set_state('INPUTS_VERIFIED')

    def _build_staging(self):
        from engine.recipe_runtime import build
        self._set_state('BUILDING_CLEAN_BASE')
        self._set_state('APPLYING_PROJECT_TRANSFORMATIONS')
        build(self.bundle, self.selection, self.session_dir / 'source_recipe_work', self.staging_root)
        self.staged_count = len(self.records)
        self._set_state('STAGING_BUILT')

    def _recheck_preconditions(self):
        legacy.safe_chain(self.pack_path)
        require(self.bundle is not None and core.sha256_file(self.pack_path) == self.bundle.sha256, 'PACK_CHANGED_BEFORE_COMMIT')
        super()._recheck_preconditions()

    def run(self):
        result = super().run()
        result.details['ownership_policy'] = 'MANIFEST_ROOTS_PLUS_TWO_RETIRED_ROOTS_ONLY'
        result.details['retired_product_roots'] = sorted(self.RETIRED_PRODUCT_ROOTS)
        result.details['preserved_independent_entities'] = self.preserved_files
        if self.bundle is not None:
            result.details['content_identity'] = self.bundle.identity()
        return result
