#!/usr/bin/env python3
"""DBM-RV*+ deterministic local patch engine — Phase 8 prototype.

Python standard library only.  The engine validates exact public S01 and S08
archives, stages the complete canonical result outside the live AddOns tree,
and preserves the frozen Phase 4 transaction and rollback semantics.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import sys
import time
import uuid
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ENGINE_VERSION = "1.3.0-phase8-prototype"
MANIFEST_SHA256 = "e24ee7fd08c4e2383e121e66c319794bb998d06675a70c9132695d2cba3eae3c"
BASELINE_MODEL_SHA256 = "e431b69140047702948cc715cc0cbe23cde3dc5e1e3766b9765eee491d9d9e5d"
SOURCE_SHA256 = {
    "S01": "403fcf41191742f224b9eecea34295437f3425527f26e42af101538de6416be9",
    "S08": "5cf0b8ade4f35c15b6c83f34de7f40aaab0339f250af2552131028e425ecf1fe",
}
EXPECTED_RECORDS = 119
EXPECTED_EXISTING = 73
EXPECTED_ABSENT = 46
EXPECTED_MANAGED_OUTPUT_DIGEST_SHA256 = "6d12351f2f2f38eee6d6767d5a873d0e8f7b94fec754f5f28f87e9da6b45cf64"
ALLOWED_PROJECT_PATHS = {
    'DBM-RV-Sounds/DBM-RV-Sounds.lua',
    'DBM-RV-Sounds/DBM-RV-Sounds.toc',
    'DBM-RV-Sounds/Licenses/CC-BY-3.0.txt',
    'DBM-RV-Sounds/Licenses/CC0-1.0.txt',
    'DBM-RV-Sounds/Licenses/sArena_Reloaded-MIT.txt',
    'DBM-RV-Sounds/Sounds/AirHorn.ogg',
    'DBM-RV-Sounds/Sounds/Applause.ogg',
    'DBM-RV-Sounds/Sounds/Blast.ogg',
    'DBM-RV-Sounds/Sounds/Bleat.ogg',
    'DBM-RV-Sounds/Sounds/BoxingArenaSound.ogg',
    'DBM-RV-Sounds/Sounds/CartoonVoiceBaritone.ogg',
    'DBM-RV-Sounds/Sounds/CartoonWalking.ogg',
    'DBM-RV-Sounds/Sounds/CatMeow2.ogg',
    'DBM-RV-Sounds/Sounds/CowMooing.ogg',
    'DBM-RV-Sounds/Sounds/HeartbeatSingle.ogg',
    'DBM-RV-Sounds/Sounds/KittenMeow.ogg',
    'DBM-RV-Sounds/Sounds/LossaHealerTrinket.ogg',
    'DBM-RV-Sounds/Sounds/LossaTrinket.ogg',
    'DBM-RV-Sounds/Sounds/RingingPhone.ogg',
    'DBM-RV-Sounds/Sounds/RoaringLion.ogg',
    'DBM-RV-Sounds/Sounds/RobotBlip.ogg',
    'DBM-RV-Sounds/Sounds/Shotgun.ogg',
    'DBM-RV-Sounds/Sounds/TempleBellHuge.ogg',
    'DBM-RV-Sounds/Sounds/Torch.ogg',
    'DBM-RV-Sounds/Sounds/WarningSiren.ogg',
    'DBM-RV-Sounds/Sounds/WaterDrop.ogg',
    'DBM-RV-Sounds/THIRD_PARTY_NOTICES.txt',
    'DBM-RV-UWoW-BFA-Sounds/DBM-RV-UWoW-BFA-Sounds.lua',
    'DBM-RV-UWoW-BFA-Sounds/DBM-RV-UWoW-BFA-Sounds.toc',
    'DBM-RV-UWoW-Compat/Compat.lua',
    'DBM-RV-UWoW-Compat/DBM-RV-UWoW-Compat.toc',
}
EXPECTED_OPERATION_COUNTS = {
    "PATCH_VERIFIED_SOURCE_FILE": 52,
    "PATCH_VERIFIED_PUBLIC_SOURCE_FILE": 36,
    "ADD_PROJECT_FILE": 31,
}


class EngineFailure(Exception):
    outcome = "INTERNAL_ERROR"

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail


class BaselineFailure(EngineFailure):
    outcome = "BASELINE_MISMATCH"


class StagingFailure(EngineFailure):
    outcome = "STAGING_FAILED"


class BackupFailure(EngineFailure):
    outcome = "BACKUP_FAILED"


class ApplyFailure(EngineFailure):
    outcome = "APPLY_FAILED"


class VerifyFailure(EngineFailure):
    outcome = "VERIFY_FAILED"


class UnsafePathFailure(EngineFailure):
    outcome = "FAILED_NO_WRITES"


@dataclass
class FaultPlan:
    target_changed_after_staging: bool = False
    backup_failure: bool = False
    mid_commit_after: int | None = None
    post_commit_corruption: bool = False


@dataclass
class RunResult:
    outcome: str
    reason_code: str | None
    rollback_status: str | None
    session_dir: Path
    target_write_count: int
    commit_write_count: int
    staged_count: int
    verified_count: int
    backup_existing_count: int
    backup_absent_count: int
    backup_root: Path | None
    managed_output_digest_sha256: str | None
    target_tree_post_digest_sha256: str | None
    state: str
    details: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "engine_version": ENGINE_VERSION,
            "outcome": self.outcome,
            "reason_code": self.reason_code,
            "rollback_status": self.rollback_status,
            "session_dir": str(self.session_dir),
            "target_write_count": self.target_write_count,
            "commit_write_count": self.commit_write_count,
            "staged_count": self.staged_count,
            "verified_count": self.verified_count,
            "backup_existing_count": self.backup_existing_count,
            "backup_absent_count": self.backup_absent_count,
            "backup_root": str(self.backup_root) if self.backup_root else None,
            "managed_output_digest_sha256": self.managed_output_digest_sha256,
            "target_tree_post_digest_sha256": self.target_tree_post_digest_sha256,
            "state": self.state,
            "details": self.details,
        }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def aggregate_digest(entries: dict[str, str]) -> str:
    canonical = "".join(f"{path}\0{entries[path]}\n" for path in sorted(entries))
    return sha256_bytes(canonical.encode("utf-8"))


def snapshot_tree_digest(root: Path) -> str:
    entries: dict[str, str] = {}
    for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        for name in list(dirs):
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            if is_reparse(path):
                entries[relative + "/"] = "REPARSE"
                dirs.remove(name)
        for name in files:
            path = current_path / name
            relative = path.relative_to(root).as_posix()
            entries[relative] = "REPARSE" if is_reparse(path) else sha256_file(path)
    return aggregate_digest(entries)


def is_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    try:
        info = os.lstat(path)
    except FileNotFoundError:
        return False
    attrs = getattr(info, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attrs & flag)


def safe_relative_path(raw: str) -> PurePosixPath:
    if not isinstance(raw, str) or not raw or "\\" in raw or "\x00" in raw:
        raise UnsafePathFailure("UNSAFE_PATH", f"invalid relative path: {raw!r}")
    p = PurePosixPath(raw)
    if p.is_absolute() or raw.startswith("/") or ":" in p.parts[0]:
        raise UnsafePathFailure("PATH_TRAVERSAL_REJECTED", raw)
    if any(part in ("", ".", "..") for part in p.parts):
        raise UnsafePathFailure("PATH_TRAVERSAL_REJECTED", raw)
    return p


def assert_within(root: Path, relative: PurePosixPath) -> Path:
    candidate = root.joinpath(*relative.parts)
    root_resolved = root.resolve(strict=True)
    parent = candidate.parent.resolve(strict=False)
    try:
        parent.relative_to(root_resolved)
    except ValueError as exc:
        raise UnsafePathFailure("PATH_ESCAPE_REJECTED", str(relative)) from exc
    return candidate


def assert_no_reparse_chain(root: Path, relative: PurePosixPath | None = None) -> None:
    if is_reparse(root):
        raise BaselineFailure("UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(root))
    current = root
    parts = relative.parts if relative is not None else ()
    for part in parts:
        current = current / part
        if current.exists() or current.is_symlink():
            if is_reparse(current):
                raise BaselineFailure(
                    "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(current)
                )
        else:
            break


def validate_record_paths(records: Iterable[dict[str, Any]]) -> list[PurePosixPath]:
    paths: list[PurePosixPath] = []
    folded: dict[str, str] = {}
    for record in records:
        raw = record.get("target_relative_path")
        path = safe_relative_path(raw)
        key = "/".join(path.parts).casefold()
        if key in folded:
            raise UnsafePathFailure(
                "WINDOWS_CASEFOLD_COLLISION", f"{folded[key]!r} and {raw!r}"
            )
        folded[key] = raw
        paths.append(path)
    return paths


def load_pinned_json(path: Path, expected_sha: str, kind: str) -> dict[str, Any]:
    if not path.is_file():
        raise BaselineFailure(f"{kind}_MISSING", str(path))
    actual = sha256_file(path)
    if actual != expected_sha:
        reason = "MANIFEST_INTEGRITY_MISMATCH" if kind == "MANIFEST" else "BASELINE_MODEL_INTEGRITY_MISMATCH"
        raise BaselineFailure(reason, f"expected {expected_sha}, got {actual}")
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineFailure(f"{kind}_INVALID_JSON", str(exc)) from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    path.write_text(data, encoding="utf-8", newline="\n")


class SessionLogger:
    def __init__(self, session_dir: Path) -> None:
        self.session_dir = session_dir
        self.log_path = session_dir / "session.log.jsonl"
        self.sequence = 0

    def emit(self, event: str, **fields: Any) -> None:
        self.sequence += 1
        record = {
            "sequence": self.sequence,
            "time_unix_ns": time.time_ns(),
            "event": event,
            **fields,
        }
        with self.log_path.open("a", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")


class PatchEngine:
    def __init__(
        self,
        *,
        target_root: Path,
        manifest_path: Path,
        baseline_model_path: Path,
        source_s01: Path,
        source_s08: Path,
        project_payload_root: Path,
        session_parent: Path,
        check_only: bool = False,
        fault: FaultPlan | None = None,
    ) -> None:
        self.target_root = target_root.absolute()
        self.manifest_path = manifest_path.absolute()
        self.baseline_model_path = baseline_model_path.absolute()
        self.source_paths = {"S01": source_s01.absolute(), "S08": source_s08.absolute()}
        self.project_payload_root = project_payload_root.absolute()
        self.session_parent = session_parent.absolute()
        self.check_only = check_only
        self.fault = fault or FaultPlan()
        # Keep the external session path short enough for legacy Windows path limits.
        self.session_id = uuid.uuid4().hex[:12]
        self.session_dir = self.session_parent / self.session_id
        self.staging_root = self.session_dir / "staging"
        self.backup_root = self.session_dir / "backup"
        self.logger: SessionLogger | None = None
        self.state = "INIT"
        self.records: list[dict[str, Any]] = []
        self.record_paths: list[PurePosixPath] = []
        self.baseline: dict[str, Any] = {}
        self.manifest: dict[str, Any] = {}
        self.source_zips: dict[str, zipfile.ZipFile] = {}
        self.source_members: dict[str, dict[str, zipfile.ZipInfo]] = {}
        self.backup_manifest: list[dict[str, Any]] = []
        self.committed: list[PurePosixPath] = []
        self.created_dirs: list[Path] = []
        self.commit_started = False
        self.target_write_count = 0
        self.commit_write_count = 0
        self.staged_count = 0
        self.verified_count = 0
        self.managed_output_digest_sha256: str | None = None
        self.target_tree_post_digest_sha256: str | None = None
        self.already_patched = False

    def _set_state(self, state: str) -> None:
        self.state = state
        assert self.logger is not None
        self.logger.emit("STATE_TRANSITION", state=state)

    def _new_session(self) -> None:
        try:
            self.session_parent.resolve(strict=False).relative_to(
                self.target_root.resolve(strict=True)
            )
        except ValueError:
            pass
        else:
            raise UnsafePathFailure(
                "SESSION_DIRECTORY_INSIDE_TARGET_ROOT", str(self.session_parent)
            )
        self.session_parent.mkdir(parents=True, exist_ok=True)
        assert_no_reparse_chain(self.session_parent)
        self.session_dir.mkdir(parents=False, exist_ok=False)
        self.staging_root.mkdir()
        self.logger = SessionLogger(self.session_dir)
        self.logger.emit(
            "ENGINE_START",
            engine_version=ENGINE_VERSION,
            session_id=self.session_id,
            target_root=str(self.target_root),
            backup_root=str(self.backup_root),
        )

    def _validate_inputs(self) -> None:
        if not self.target_root.is_dir():
            raise BaselineFailure("TARGET_ROOT_MISSING", str(self.target_root))
        assert_no_reparse_chain(self.target_root)
        if not self.project_payload_root.is_dir() or is_reparse(self.project_payload_root):
            raise BaselineFailure("PROJECT_PAYLOAD_ROOT_UNSAFE_OR_MISSING", str(self.project_payload_root))
        for source in (self.manifest_path, self.baseline_model_path):
            if is_reparse(source):
                raise BaselineFailure("INPUT_PATH_UNSAFE_ENTITY", str(source))
        self.manifest = load_pinned_json(self.manifest_path, MANIFEST_SHA256, "MANIFEST")
        self.baseline = load_pinned_json(
            self.baseline_model_path, BASELINE_MODEL_SHA256, "BASELINE_MODEL"
        )
        self.records = self.manifest.get("records", [])
        if len(self.records) != EXPECTED_RECORDS:
            raise BaselineFailure("MANIFEST_RECORD_COUNT_MISMATCH", str(len(self.records)))
        self.record_paths = validate_record_paths(self.records)
        actual_counts: dict[str, int] = {}
        for record in self.records:
            operation = record["operation_type"]
            actual_counts[operation] = actual_counts.get(operation, 0) + 1
            if record.get("source_id") in {"S02", "S04"}:
                raise BaselineFailure("HISTORICAL_RUNTIME_SOURCE_FORBIDDEN", record["target_relative_path"])
        if actual_counts != EXPECTED_OPERATION_COUNTS:
            raise BaselineFailure("MANIFEST_OPERATION_COUNT_MISMATCH", str(actual_counts))

        # The bundled project payload is part of the trusted prototype package.
        # Validate it before allowing an ALREADY_PATCHED short circuit.
        for record in self.records:
            if record["operation_type"] == "ADD_PROJECT_FILE":
                self._read_payload_file(self.project_payload_root, record, "PROJECT_PAYLOAD")

        if self._detect_exact_post_state():
            self.already_patched = True
            self._set_state("ALREADY_PATCHED")
            return

        for source_id, path in self.source_paths.items():
            if not path.is_file():
                raise BaselineFailure(f"SOURCE_{source_id}_MISSING", str(path))
            if is_reparse(path):
                raise BaselineFailure(f"SOURCE_{source_id}_UNSAFE_ENTITY", str(path))
            actual = sha256_file(path)
            if actual != SOURCE_SHA256[source_id]:
                raise BaselineFailure(
                    f"SOURCE_{source_id}_SHA_MISMATCH",
                    f"expected {SOURCE_SHA256[source_id]}, got {actual}",
                )
            try:
                archive = zipfile.ZipFile(path, "r")
                bad_member = archive.testzip()
                if bad_member is not None:
                    raise zipfile.BadZipFile(f"CRC failure: {bad_member}")
            except (OSError, zipfile.BadZipFile) as exc:
                raise BaselineFailure(f"SOURCE_{source_id}_ARCHIVE_MALFORMED", str(exc)) from exc
            self.source_zips[source_id] = archive
            self.source_members[source_id] = self._validate_zip_member_names(archive)

        for record in self.records:
            source_id = record.get("source_id")
            if source_id in self.source_zips:
                identity = record["source_identity"]
                if identity.get("archive_sha256") != SOURCE_SHA256[source_id]:
                    raise BaselineFailure("SOURCE_IDENTITY_ARCHIVE_MISMATCH", record["target_relative_path"])
                self._read_source_member(
                    source_id,
                    identity["source_relative_path"],
                    identity["source_file_sha256"],
                )
        self._set_state("INPUTS_VERIFIED")

    def _detect_exact_post_state(self) -> bool:
        """Return true only for the complete exact managed Phase 8 post-state."""
        profile = self.baseline["verification_profiles"]["EXTRACTED_ADDONS_TREE_STRICT"]
        expected: dict[str, str] = {
            entry["path"]: entry["sha256"] for entry in profile["file_manifest"]
        }
        managed: dict[str, str] = {}
        for record in self.records:
            expected[record["target_relative_path"]] = record["result_file_sha256"]
            managed[record["target_relative_path"]] = record["result_file_sha256"]

        managed_digest = aggregate_digest(managed)
        if managed_digest != EXPECTED_MANAGED_OUTPUT_DIGEST_SHA256:
            raise BaselineFailure(
                "EXPECTED_POST_STATE_DIGEST_MISMATCH",
                f"expected {EXPECTED_MANAGED_OUTPUT_DIGEST_SHA256}, got {managed_digest}",
            )

        roots = set(profile["managed_roots"])
        roots.update(safe_relative_path(path).parts[0] for path in expected)
        actual_paths: set[str] = set()
        for root_name in sorted(roots):
            rel_root = safe_relative_path(root_name)
            root = assert_within(self.target_root, rel_root)
            if not root.exists():
                return False
            if not root.is_dir() or is_reparse(root):
                raise BaselineFailure(
                    "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(root)
                )
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                current_path = Path(current)
                for name in list(dirs):
                    path = current_path / name
                    if is_reparse(path):
                        raise BaselineFailure(
                            "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(path)
                        )
                for name in files:
                    path = current_path / name
                    if is_reparse(path) or not path.is_file():
                        raise BaselineFailure(
                            "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(path)
                        )
                    actual_paths.add(path.relative_to(self.target_root).as_posix())

        if actual_paths != set(expected):
            return False
        for relative, expected_hash in expected.items():
            path = assert_within(self.target_root, safe_relative_path(relative))
            if sha256_file(path) != expected_hash:
                return False

        self.managed_output_digest_sha256 = managed_digest
        self.target_tree_post_digest_sha256 = snapshot_tree_digest(self.target_root)
        assert self.logger is not None
        self.logger.emit(
            "EXACT_POST_STATE_VERIFIED",
            managed_file_count=len(managed),
            managed_output_digest_sha256=managed_digest,
            target_tree_post_digest_sha256=self.target_tree_post_digest_sha256,
        )
        return True

    def _validate_zip_member_names(self, archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
        result: dict[str, zipfile.ZipInfo] = {}
        folded: dict[str, str] = {}
        for info in archive.infolist():
            if info.is_dir():
                continue
            unix_mode = (info.external_attr >> 16) & 0xFFFF
            if unix_mode and stat.S_ISLNK(unix_mode):
                raise BaselineFailure("SOURCE_ARCHIVE_UNSAFE_ENTITY", info.filename)
            p = safe_relative_path(info.filename)
            name = "/".join(p.parts)
            key = name.casefold()
            if key in folded:
                raise BaselineFailure("SOURCE_ARCHIVE_PATH_COLLISION", name)
            folded[key] = name
            result[name] = info
        return result

    def _verify_baseline(self) -> None:
        profile = self.baseline["verification_profiles"]["EXTRACTED_ADDONS_TREE_STRICT"]
        expected = {entry["path"]: entry for entry in profile["file_manifest"]}
        actual_paths: set[str] = set()
        for root_name in profile["managed_roots"]:
            rel_root = safe_relative_path(root_name)
            root = assert_within(self.target_root, rel_root)
            if not root.is_dir():
                raise BaselineFailure("UPSTREAM_MANAGED_FILE_MISSING", root_name)
            assert_no_reparse_chain(self.target_root, rel_root)
            for current, dirs, files in os.walk(root, topdown=True, followlinks=False):
                current_path = Path(current)
                for name in list(dirs):
                    p = current_path / name
                    if is_reparse(p):
                        raise BaselineFailure(
                            "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(p)
                        )
                for name in files:
                    p = current_path / name
                    if is_reparse(p) or not p.is_file():
                        raise BaselineFailure(
                            "UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", str(p)
                        )
                    rel = p.relative_to(self.target_root).as_posix()
                    key = rel.casefold()
                    if any(key == other.casefold() and rel != other for other in actual_paths):
                        raise BaselineFailure("UPSTREAM_MANAGED_PATH_COLLISION_OR_UNSAFE_ENTITY", rel)
                    actual_paths.add(rel)
        expected_paths = set(expected)
        missing = sorted(expected_paths - actual_paths)
        unexpected = sorted(actual_paths - expected_paths)
        if missing:
            raise BaselineFailure("UPSTREAM_MANAGED_FILE_MISSING", missing[0])
        if unexpected:
            raise BaselineFailure("UPSTREAM_MANAGED_UNEXPECTED_FILE", unexpected[0])
        if len(actual_paths) != profile["expected_managed_file_count"]:
            raise BaselineFailure("UPSTREAM_MANAGED_FILE_COUNT_MISMATCH", str(len(actual_paths)))
        for rel, entry in expected.items():
            path = assert_within(self.target_root, safe_relative_path(rel))
            if path.stat().st_size != entry["size_bytes"] or sha256_file(path) != entry["sha256"]:
                raise BaselineFailure("UPSTREAM_MANAGED_FILE_HASH_MISMATCH", rel)

        pre = self.baseline["target_clean_preconditions"]
        for entry in pre["file_sha256_paths"]:
            rel = safe_relative_path(entry["path"])
            path = assert_within(self.target_root, rel)
            assert_no_reparse_chain(self.target_root, rel)
            if not path.is_file() or sha256_file(path) != entry["sha256"]:
                raise BaselineFailure("TARGET_PRECONDITION_HASH_MISMATCH", entry["path"])
        for raw in pre["must_be_absent_paths"]:
            rel = safe_relative_path(raw)
            path = assert_within(self.target_root, rel)
            assert_no_reparse_chain(self.target_root, rel)
            if path.exists() or path.is_symlink():
                raise BaselineFailure("TARGET_EXPECTED_ABSENT_PRESENT", raw)
        for raw in pre["addition_roots_must_be_absent"]:
            rel = safe_relative_path(raw)
            path = assert_within(self.target_root, rel)
            if path.exists() or path.is_symlink():
                raise BaselineFailure("TARGET_ADDITION_ROOT_PRESENT", raw)
        self._set_state("BASELINE_VERIFIED")

    def _apply_patch_record(self, record: dict[str, Any], source: bytes) -> bytes:
        source = self._prepare_source(record, source)
        if sha256_bytes(source) != record["baseline_file_sha256"]:
            raise StagingFailure("SOURCE_BASELINE_HASH_MISMATCH", record["target_relative_path"])
        try:
            text = source.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StagingFailure("SOURCE_UTF8_DECODE_FAILED", record["target_relative_path"]) from exc
        edits: list[tuple[int, int, str]] = []
        for index, op in enumerate(record.get("operations", []), start=1):
            if op.get("operation_type") != "REPLACE_EXACT_BLOCK":
                raise StagingFailure("UNSUPPORTED_OPERATION", str(op.get("operation_type")))
            match = op["match_text"]
            replacement = op["replacement_text"]
            if sha256_bytes(match.encode("utf-8")) != op["match_sha256"]:
                raise StagingFailure("MATCH_PAYLOAD_HASH_MISMATCH", f"{record['target_relative_path']}#{index}")
            if sha256_bytes(replacement.encode("utf-8")) != op["replacement_sha256"]:
                raise StagingFailure("REPLACEMENT_PAYLOAD_HASH_MISMATCH", f"{record['target_relative_path']}#{index}")
            count = text.count(match)
            if count != op.get("expected_occurrence_count", 1) or count != 1:
                raise StagingFailure(
                    "EXACT_ANCHOR_OCCURRENCE_MISMATCH",
                    f"{record['target_relative_path']}#{index}: expected 1, got {count}",
                )
            start = text.find(match)
            edits.append((start, start + len(match), replacement))
        ordered = sorted(edits, key=lambda item: item[0], reverse=True)
        for previous, current in zip(ordered, ordered[1:]):
            if current[1] > previous[0]:
                raise StagingFailure("OVERLAPPING_EXACT_ANCHORS", record["target_relative_path"])
        result = text
        for start, end, replacement in ordered:
            result = result[:start] + replacement + result[end:]
        return result.encode("utf-8")

    def _prepare_source(self, record: dict[str, Any], source: bytes) -> bytes:
        prepared = source
        for index, operation in enumerate(record.get("preparation", []), start=1):
            if operation.get("operation_type") != "NORMALIZE_NEWLINES_TO_LF":
                raise StagingFailure("UNSUPPORTED_PREPARATION", f"{record['target_relative_path']}#{index}")
            try:
                text = prepared.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise StagingFailure("SOURCE_UTF8_DECODE_FAILED", record["target_relative_path"]) from exc
            crlf_count = text.count("\r\n")
            lone_cr_count = text.count("\r") - crlf_count
            if crlf_count != operation["expected_crlf_count"] or lone_cr_count != operation["expected_lone_cr_count"]:
                raise StagingFailure("SOURCE_NEWLINE_PRECONDITION_MISMATCH", record["target_relative_path"])
            prepared = text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
            if sha256_bytes(prepared) != operation["result_sha256"]:
                raise StagingFailure("SOURCE_PREPARATION_HASH_MISMATCH", record["target_relative_path"])
        return prepared

    def _read_source_member(self, source_id: str, raw_path: str, expected_sha: str) -> bytes:
        archive = self.source_zips.get(source_id)
        if archive is None:
            raise BaselineFailure("SOURCE_ID_UNKNOWN", source_id)
        members = self.source_members[source_id]
        member_path = "/".join(safe_relative_path(raw_path).parts)
        info = members.get(member_path)
        if info is None:
            raise BaselineFailure("SOURCE_REQUIRED_PATH_MISSING", member_path)
        data = archive.read(info)
        if sha256_bytes(data) != expected_sha:
            raise BaselineFailure("SOURCE_REQUIRED_FILE_HASH_MISMATCH", member_path)
        return data

    def _read_payload_file(self, root: Path, record: dict[str, Any], kind: str) -> bytes:
        op = record["operations"][0]
        raw = op["payload_relative_path"]
        if kind == "PROJECT_PAYLOAD" and raw not in ALLOWED_PROJECT_PATHS:
            raise StagingFailure("PROJECT_PAYLOAD_PATH_NOT_ALLOWED", raw)
        if kind == "PHASE6_OGG" and raw not in {
            "DBM-RV-Sounds/Sounds/Cat.ogg",
            "DBM-RV-Sounds/Sounds/Hyena.ogg",
            "DBM-RV-Sounds/Sounds/Phone.ogg",
            "DBM-RV-Sounds/Sounds/WarningSiren.ogg",
            "DBM-RV-Sounds/Sounds/WickedMaleLaugh.ogg",
        }:
            raise StagingFailure("PHASE6_OGG_PATH_NOT_ALLOWED", raw)
        rel = safe_relative_path(raw)
        assert_no_reparse_chain(root, rel)
        path = assert_within(root, rel)
        if not path.is_file():
            raise StagingFailure(f"{kind}_MISSING", raw)
        data = path.read_bytes()
        if sha256_bytes(data) != op["payload_sha256"]:
            raise StagingFailure(f"{kind}_HASH_MISMATCH", raw)
        return data

    def _build_staging(self) -> None:
        for record, rel in zip(self.records, self.record_paths):
            operation = record["operation_type"]
            if operation in {"PATCH_VERIFIED_SOURCE_FILE", "PATCH_VERIFIED_PUBLIC_SOURCE_FILE"}:
                identity = record["source_identity"]
                source = self._read_source_member(
                    record["source_id"],
                    identity["source_relative_path"],
                    identity["source_file_sha256"],
                )
                data = self._apply_patch_record(record, source)
            elif operation == "ADD_PROJECT_FILE":
                data = self._read_payload_file(self.project_payload_root, record, "PROJECT_PAYLOAD")
            else:
                raise StagingFailure("UNSUPPORTED_OPERATION", str(operation))
            if len(data) != record["result_size_bytes"]:
                raise StagingFailure("STAGED_SIZE_MISMATCH", record["target_relative_path"])
            if sha256_bytes(data) != record["result_file_sha256"]:
                raise StagingFailure("STAGED_RESULT_HASH_MISMATCH", record["target_relative_path"])
            destination = self.staging_root.joinpath(*rel.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            self.staged_count += 1
        self._set_state("STAGING_BUILT")

    def _verify_staging(self) -> None:
        staged_files = {
            p.relative_to(self.staging_root).as_posix()
            for p in self.staging_root.rglob("*")
            if p.is_file()
        }
        expected = {r["target_relative_path"] for r in self.records}
        if staged_files != expected:
            raise StagingFailure("STAGING_ALLOWLIST_MISMATCH", "staged path set mismatch")
        validate_record_paths(self.records)
        for record, rel in zip(self.records, self.record_paths):
            path = self.staging_root.joinpath(*rel.parts)
            if path.stat().st_size != record["result_size_bytes"]:
                raise StagingFailure("STAGING_VERIFY_SIZE_MISMATCH", record["target_relative_path"])
            if sha256_file(path) != record["result_file_sha256"]:
                raise StagingFailure("STAGING_VERIFY_HASH_MISMATCH", record["target_relative_path"])
        self._set_state("STAGING_VERIFIED")

    def _recheck_preconditions(self) -> None:
        if self.fault.target_changed_after_staging:
            record = next(r for r in self.records if r["target_clean_upstream_precondition"]["state"] == "FILE_SHA256")
            path = assert_within(self.target_root, safe_relative_path(record["target_relative_path"]))
            path.write_bytes(path.read_bytes() + b"\n-- deterministic TOCTOU test fault\n")
        for source_id, source_path in self.source_paths.items():
            if sha256_file(source_path) != SOURCE_SHA256[source_id]:
                raise BaselineFailure(f"SOURCE_{source_id}_CHANGED_BEFORE_COMMIT", str(source_path))
        for record in self.records:
            if record["operation_type"] == "ADD_PROJECT_FILE":
                self._read_payload_file(self.project_payload_root, record, "PROJECT_PAYLOAD")
        for record, rel in zip(self.records, self.record_paths):
            path = assert_within(self.target_root, rel)
            assert_no_reparse_chain(self.target_root, rel)
            pre = record["target_clean_upstream_precondition"]
            if pre["state"] == "FILE_SHA256":
                if not path.is_file() or sha256_file(path) != pre["sha256"]:
                    raise BaselineFailure("TARGET_PRECONDITION_HASH_MISMATCH", record["target_relative_path"])
            elif pre["state"] == "MUST_BE_ABSENT":
                if path.exists() or path.is_symlink():
                    raise BaselineFailure("TARGET_EXPECTED_ABSENT_PRESENT", record["target_relative_path"])
            else:
                raise BaselineFailure("TARGET_PRECONDITION_UNKNOWN", str(pre["state"]))
        self._set_state("PRECOMMIT_RECHECKED")

    def _backup(self) -> None:
        existing = 0
        absent = 0
        if self.backup_root.parent != self.session_dir:
            raise BackupFailure("BACKUP_LOCATION_POLICY_MISMATCH", str(self.backup_root))
        self.backup_root.mkdir(parents=True, exist_ok=False)
        assert_no_reparse_chain(self.backup_root)
        for record, rel in zip(self.records, self.record_paths):
            target = assert_within(self.target_root, rel)
            pre = record["target_clean_upstream_precondition"]
            if pre["state"] == "FILE_SHA256":
                backup = self.backup_root.joinpath(*rel.parts)
                backup.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(target, backup, follow_symlinks=False)
                actual = sha256_file(backup)
                if actual != pre["sha256"]:
                    raise BackupFailure("BACKUP_HASH_MISMATCH", record["target_relative_path"])
                self.backup_manifest.append(
                    {
                        "relative_path": record["target_relative_path"],
                        "pre_state": "FILE",
                        "sha256": actual,
                        "size_bytes": backup.stat().st_size,
                        "backup_relative_path": backup.relative_to(self.backup_root).as_posix(),
                    }
                )
                existing += 1
            else:
                self.backup_manifest.append(
                    {
                        "relative_path": record["target_relative_path"],
                        "pre_state": "ABSENT",
                        "sha256": None,
                        "size_bytes": 0,
                        "backup_relative_path": None,
                    }
                )
                absent += 1
        if existing != EXPECTED_EXISTING or absent != EXPECTED_ABSENT:
            raise BackupFailure("BACKUP_RECORD_COUNT_MISMATCH", f"{existing}/{absent}")
        write_json(self.session_dir / "backup_manifest.json", self.backup_manifest)
        write_json(self.backup_root / "backup_manifest.json", self.backup_manifest)
        if self.fault.backup_failure:
            raise BackupFailure("INJECTED_BACKUP_FAILURE", "deterministic test fault")
        self._set_state("BACKUP_COMPLETE")

    def _mkdir_tracked(self, parent: Path) -> None:
        pending: list[Path] = []
        current = parent
        while not current.exists():
            pending.append(current)
            current = current.parent
        for path in reversed(pending):
            path.mkdir()
            self.created_dirs.append(path)

    def _atomic_write(self, destination: Path, data: bytes) -> None:
        self._mkdir_tracked(destination.parent)
        tmp = destination.parent / f".{destination.name}.dbmrvpatch.{self.session_id}.tmp"
        try:
            with tmp.open("xb") as handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, destination)
        finally:
            if tmp.exists():
                tmp.unlink()

    def _commit(self) -> None:
        ordered = sorted(zip(self.records, self.record_paths), key=lambda pair: pair[0]["target_relative_path"])
        self.commit_started = True
        self._set_state("COMMIT_IN_PROGRESS")
        for record, rel in ordered:
            target = assert_within(self.target_root, rel)
            assert_no_reparse_chain(self.target_root, rel.parent if len(rel.parts) > 1 else None)
            pre = record["target_clean_upstream_precondition"]
            if pre["state"] == "FILE_SHA256":
                if not target.is_file() or sha256_file(target) != pre["sha256"]:
                    raise ApplyFailure("TARGET_CHANGED_DURING_COMMIT", record["target_relative_path"])
            elif target.exists() or target.is_symlink():
                raise ApplyFailure("ABSENT_TARGET_APPEARED_DURING_COMMIT", record["target_relative_path"])
            staged = self.staging_root.joinpath(*rel.parts).read_bytes()
            self._atomic_write(target, staged)
            self.committed.append(rel)
            self.commit_write_count += 1
            self.target_write_count += 1
            assert self.logger is not None
            self.logger.emit(
                "TARGET_COMMIT",
                relative_path=record["target_relative_path"],
                sha256=record["result_file_sha256"],
            )
            if self.fault.mid_commit_after is not None and self.commit_write_count >= self.fault.mid_commit_after:
                raise ApplyFailure("INJECTED_MID_COMMIT_FAILURE", str(self.commit_write_count))
        self._set_state("COMMIT_COMPLETE")
        if self.fault.post_commit_corruption:
            first = assert_within(self.target_root, self.committed[0])
            with first.open("ab") as handle:
                handle.write(b"INJECTED_POST_COMMIT_CORRUPTION")
                handle.flush()
                os.fsync(handle.fileno())
            self.target_write_count += 1

    def _verify_commit(self) -> None:
        verified = 0
        managed: dict[str, str] = {}
        for record, rel in zip(self.records, self.record_paths):
            target = assert_within(self.target_root, rel)
            if not target.is_file() or target.stat().st_size != record["result_size_bytes"]:
                raise VerifyFailure("COMMIT_SIZE_MISMATCH", record["target_relative_path"])
            actual = sha256_file(target)
            if actual != record["result_file_sha256"]:
                raise VerifyFailure("COMMIT_HASH_MISMATCH", record["target_relative_path"])
            managed[record["target_relative_path"]] = actual
            verified += 1
        self.verified_count = verified
        self.managed_output_digest_sha256 = aggregate_digest(managed)
        self.target_tree_post_digest_sha256 = snapshot_tree_digest(self.target_root)
        assert self.logger is not None
        self.logger.emit(
            "POST_RUN_AGGREGATE_DIGEST",
            requirement_id="P5-REQ-AGG-001",
            managed_file_count=verified,
            managed_output_digest_sha256=self.managed_output_digest_sha256,
            target_tree_post_digest_sha256=self.target_tree_post_digest_sha256,
        )
        self._set_state("COMMIT_VERIFIED")

    def _rollback(self) -> str:
        self._set_state("ROLLBACK_IN_PROGRESS")
        try:
            ordered_entries = sorted(
                self.backup_manifest,
                key=lambda entry: entry["relative_path"],
                reverse=True,
            )
            for entry in ordered_entries:
                raw = entry["relative_path"]
                rel = safe_relative_path(raw)
                target = assert_within(self.target_root, rel)
                if entry["pre_state"] == "FILE":
                    backup = self.backup_root / entry["backup_relative_path"]
                    self._atomic_write(target, backup.read_bytes())
                elif target.exists() or target.is_symlink():
                    if target.is_dir() and not target.is_symlink():
                        raise RuntimeError(f"rollback target unexpectedly directory: {target}")
                    target.unlink()
            for path in sorted(self.created_dirs, key=lambda p: len(p.parts), reverse=True):
                if path.exists():
                    try:
                        path.rmdir()
                    except OSError:
                        pass
            for entry in self.backup_manifest:
                rel = safe_relative_path(entry["relative_path"])
                target = assert_within(self.target_root, rel)
                if entry["pre_state"] == "FILE":
                    if not target.is_file() or sha256_file(target) != entry["sha256"]:
                        raise RuntimeError(f"rollback hash mismatch: {entry['relative_path']}")
                elif target.exists() or target.is_symlink():
                    raise RuntimeError(f"rollback absence mismatch: {entry['relative_path']}")
            self._set_state("ROLLBACK_VERIFIED")
            return "ROLLBACK_VERIFIED"
        except Exception as exc:
            self.state = "ROLLBACK_FAILED"
            assert self.logger is not None
            self.logger.emit("ROLLBACK_FAILED", error_type=type(exc).__name__, detail=str(exc))
            return "ROLLBACK_FAILED"

    def run(self) -> RunResult:
        self._new_session()
        outcome = "INTERNAL_ERROR"
        reason: str | None = None
        rollback_status: str | None = None
        details: dict[str, Any] = {}
        try:
            self._validate_inputs()
            if self.already_patched:
                outcome = "ALREADY_PATCHED"
                reason = "EXACT_EXPECTED_POST_STATE"
            else:
                self._verify_baseline()
                self._build_staging()
                self._verify_staging()
                self._recheck_preconditions()
                if self.check_only:
                    self._set_state("READY")
                    outcome = "READY"
                else:
                    self._backup()
                    self._commit()
                    self._verify_commit()
                    self._set_state("SUCCESS")
                    outcome = "SUCCESS"
        except EngineFailure as exc:
            outcome = exc.outcome
            reason = exc.reason
            details["failure_detail"] = exc.detail
            assert self.logger is not None
            self.logger.emit(
                "ENGINE_FAILURE",
                outcome=outcome,
                reason_code=reason,
                detail=exc.detail,
                commit_started=self.commit_started,
            )
            if self.commit_started:
                rollback_status = self._rollback()
                if rollback_status == "ROLLBACK_FAILED":
                    outcome = "ROLLBACK_FAILED"
            elif self.state != "ROLLBACK_FAILED":
                self._set_state("FAILED_NO_WRITES")
        except Exception as exc:
            reason = "UNEXPECTED_ENGINE_EXCEPTION"
            if isinstance(exc, PermissionError) or (isinstance(exc, OSError) and getattr(exc, 'winerror', None) == 5):
                reason = 'ACCESS_DENIED'
                details['winerror'] = getattr(exc, 'winerror', None)
            details["failure_detail"] = f"{type(exc).__name__}: {exc}"
            assert self.logger is not None
            self.logger.emit(
                "ENGINE_FAILURE",
                outcome="INTERNAL_ERROR",
                reason_code=reason,
                error_type=type(exc).__name__,
                detail=str(exc),
                commit_started=self.commit_started,
            )
            if self.commit_started:
                rollback_status = self._rollback()
                outcome = "INTERNAL_ERROR" if rollback_status == "ROLLBACK_VERIFIED" else "ROLLBACK_FAILED"
            else:
                self._set_state("FAILED_NO_WRITES")
                outcome = "INTERNAL_ERROR"
        finally:
            for archive in self.source_zips.values():
                archive.close()
        result = RunResult(
            outcome=outcome,
            reason_code=reason,
            rollback_status=rollback_status,
            session_dir=self.session_dir,
            target_write_count=self.target_write_count,
            commit_write_count=self.commit_write_count,
            staged_count=self.staged_count,
            verified_count=self.verified_count,
            backup_existing_count=sum(1 for x in self.backup_manifest if x["pre_state"] == "FILE"),
            backup_absent_count=sum(1 for x in self.backup_manifest if x["pre_state"] == "ABSENT"),
            backup_root=self.backup_root if self.backup_manifest else None,
            managed_output_digest_sha256=self.managed_output_digest_sha256,
            target_tree_post_digest_sha256=self.target_tree_post_digest_sha256,
            state=self.state,
            details=details,
        )
        write_json(self.session_dir / "summary.json", result.as_dict())
        assert self.logger is not None
        self.logger.emit("ENGINE_END", **result.as_dict())
        return result


def fault_from_name(name: str) -> FaultPlan:
    if name == "none":
        return FaultPlan()
    if name == "target_changed_after_staging":
        return FaultPlan(target_changed_after_staging=True)
    if name == "backup_failure":
        return FaultPlan(backup_failure=True)
    if name == "mid_commit_failure":
        return FaultPlan(mid_commit_after=5)
    if name == "post_commit_corruption":
        return FaultPlan(post_commit_corruption=True)
    raise ValueError(name)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--baseline-model", required=True, type=Path)
    parser.add_argument("--source-s01", required=True, type=Path)
    parser.add_argument("--source-s08", required=True, type=Path)
    parser.add_argument("--project-payload-root", required=True, type=Path)
    parser.add_argument("--session-parent", required=True, type=Path)
    parser.add_argument(
        "--check-only",
        action="store_true",
        help="validate inputs and build/verify staging without target writes",
    )
    parser.add_argument(
        "--test-fault",
        choices=(
            "none",
            "target_changed_after_staging",
            "backup_failure",
            "mid_commit_failure",
            "post_commit_corruption",
        ),
        default="none",
        help="deterministic Phase 4C fault injection; never for user delivery",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    engine = PatchEngine(
        target_root=args.target_root,
        manifest_path=args.manifest,
        baseline_model_path=args.baseline_model,
        source_s01=args.source_s01,
        source_s08=args.source_s08,
        project_payload_root=args.project_payload_root,
        session_parent=args.session_parent,
        check_only=args.check_only,
        fault=fault_from_name(args.test_fault),
    )
    result = engine.run()
    print(json.dumps(result.as_dict(), ensure_ascii=False, sort_keys=True))
    return {
        "SUCCESS": 0,
        "READY": 0,
        "ALREADY_PATCHED": 0,
        "BASELINE_MISMATCH": 2,
        "FAILED_NO_WRITES": 2,
        "STAGING_FAILED": 3,
        "BACKUP_FAILED": 4,
        "APPLY_FAILED": 5,
        "VERIFY_FAILED": 6,
        "ROLLBACK_FAILED": 7,
        "INTERNAL_ERROR": 9,
    }.get(result.outcome, 9)


if __name__ == "__main__":
    sys.exit(main())
