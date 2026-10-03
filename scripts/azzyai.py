#!/usr/bin/env python3
"""Deterministic AzzyAI USER_AI backup and replacement primitives.

The module deliberately treats an existing USER_AI tree as user state.  A
replacement is allowed only after a fresh external backup has been copied and
compared entry-for-entry.  Backup evidence is kept separate from replacement
authority so a caller cannot turn a saved ``backup_verified`` flag into an
unrelated mutation.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
from typing import Callable, Dict, Optional, Tuple


class UnsupportedEntryError(Exception):
    """A filesystem entry cannot be compared safely."""


TreeEntry = Tuple[str, int, str]
TreeSnapshot = Dict[str, TreeEntry]
CopyFn = Callable[[Path, Path], object]


@dataclass(frozen=True)
class AzzyAiSourcePolicy:
    """Reviewed project policy for the one supported AzzyAI source state."""

    repository: str
    commit: str
    content_scope: str
    expected_tree_sha256: str


# This is the single runtime source of truth.  A candidate archive or its
# metadata must never supply the expected identity used by verification.
AUTHORIZED_AZZYAI_SOURCE = AzzyAiSourcePolicy(
    repository="https://github.com/SpenceKonde/AzzyAI",
    commit="dc0144773286d52ca5f86d774abaf3d445bc7c7b",
    content_scope="USER_AI",
    expected_tree_sha256="4f03fdabac5afa30bbe17580e6466586d94d0ba071551f8eaebecbd2716a3eda",
)


def _copy_failed(outcome: object) -> bool:
    """Reject explicit failure statuses, even if stdout says "success"."""

    if outcome is False:
        return True
    if isinstance(outcome, (int, float)) and not isinstance(outcome, bool):
        return outcome != 0
    returncode = None
    if isinstance(outcome, dict) and "returncode" in outcome:
        returncode = outcome["returncode"]
    elif hasattr(outcome, "returncode"):
        returncode = getattr(outcome, "returncode")
    if returncode is not None:
        try:
            return int(returncode) != 0
        except (TypeError, ValueError):
            return True
    if isinstance(outcome, dict) and "success" in outcome:
        return outcome["success"] is not True
    if hasattr(outcome, "success"):
        return getattr(outcome, "success") is not True
    status = None
    if isinstance(outcome, dict) and "status" in outcome:
        status = outcome["status"]
    elif hasattr(outcome, "status"):
        status = getattr(outcome, "status")
    if status is not None:
        return status not in ("ok", "passed", "success", "succeeded")
    if isinstance(outcome, str):
        return True
    return False


def _identity(path: Path, *, follow_symlinks: bool = True) -> Tuple[int, int]:
    metadata = os.stat(path, follow_symlinks=follow_symlinks)
    return metadata.st_dev, metadata.st_ino


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return False


def _has_symlink_component(path: Path) -> bool:
    """Reject lexical path aliases so a parent cannot redirect a mutation."""

    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if _is_symlink(current):
            # macOS exposes /var and /tmp as stable aliases into /private;
            # permit those OS aliases while rejecting project/user aliases.
            if current in (Path("/var"), Path("/tmp")) and os.path.realpath(current) in {
                "/private/var",
                "/private/tmp",
            }:
                continue
            return True
    return False


def _cleanup_staging(path: Path) -> None:
    """Remove only the temporary staging tree created by this transaction."""

    if _is_symlink(path):
        path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def _evidence_record(result: Dict[str, object], phase: str) -> Dict[str, object]:
    """Build descriptive evidence without copying nested authority state."""

    comparison = result.get("comparison")
    final_comparison = result.get("final_comparison")
    return {
        "schema_version": 1,
        "evidence_scope": "descriptive-only; never read as replacement authority",
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "phase": phase,
        "operation": result.get("operation"),
        "result": result.get("result"),
        "reason": result.get("reason"),
        "source": result.get("source"),
        "destination": result.get("destination"),
        "backup": result.get("backup"),
        "backup_verified": result.get("backup_verified", False),
        "replacement_authorized": result.get("replacement_authorized", False),
        "replacement_verified": result.get("replacement_verified", False),
        "comparison_status": comparison.get("status") if isinstance(comparison, dict) else None,
        "final_comparison_status": (
            final_comparison.get("status") if isinstance(final_comparison, dict) else None
        ),
    }


def _append_evidence(path: Path, result: Dict[str, object], phase: str) -> Dict[str, object]:
    """Append one durable descriptive record; callers never use it as authority."""

    try:
        if _has_symlink_component(path) or _is_symlink(path):
            raise OSError("evidence path contains an unsupported symlink component")
        path.parent.mkdir(parents=True, exist_ok=True)
        line = (json.dumps(_evidence_record(result, phase), sort_keys=True) + "\n").encode()
        fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.fchmod(fd, 0o600)
            written = 0
            while written < len(line):
                written += os.write(fd, line[written:])
            os.fsync(fd)
        finally:
            os.close(fd)
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
        return {"status": "succeeded", "path": str(path), "phase": phase}
    except OSError as exc:
        return {"status": "failed", "path": str(path), "phase": phase, "reason": str(exc)}


def _snapshot_tree(root: Path) -> TreeSnapshot:
    """Return an exact tree snapshot while rejecting symlinks and special files."""

    entries: TreeSnapshot = {}

    def visit(directory: Path, relative: Path) -> None:
        try:
            children = sorted(directory.iterdir(), key=lambda path: path.name)
        except OSError as exc:
            raise OSError(f"cannot read {directory}: {exc}") from exc

        for child in children:
            child_relative = relative / child.name
            key = child_relative.as_posix()
            try:
                if child.is_symlink():
                    raise UnsupportedEntryError(f"symbolic link is unsupported: {key}")
                if child.is_dir():
                    entries[key] = ("directory", 0, "")
                    visit(child, child_relative)
                elif child.is_file():
                    digest = hashlib.sha256()
                    size = 0
                    with child.open("rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                            size += len(chunk)
                    entries[key] = ("file", size, digest.hexdigest())
                else:
                    raise UnsupportedEntryError(f"unsupported filesystem entry: {key}")
            except OSError as exc:
                raise OSError(f"cannot inspect {child}: {exc}") from exc

    visit(root, Path("."))
    return entries


def _tree_identity(snapshot: TreeSnapshot) -> str:
    """Hash the consumed tree using stable, metadata-light canonical records."""

    records = [
        {
            "path": relative,
            "kind": entry[0],
            "size": entry[1],
            "sha256": entry[2],
        }
        for relative, entry in sorted(snapshot.items())
    ]
    encoded = json.dumps(
        records,
        ensure_ascii=True,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def source_tree_digest(path: str | Path) -> str:
    """Return the deterministic identity of a USER_AI tree without mutating it."""

    root = Path(path)
    if root.is_symlink() or not root.is_dir():
        raise UnsupportedEntryError("AzzyAI source must be a regular directory")
    if _has_symlink_component(root):
        raise UnsupportedEntryError("AzzyAI source path contains a symlink component")
    return _tree_identity(_snapshot_tree(root))


def _valid_source_policy(policy: AzzyAiSourcePolicy) -> Optional[str]:
    if policy.repository != "https://github.com/SpenceKonde/AzzyAI":
        return "authorized AzzyAI repository policy is malformed"
    if len(policy.commit) != 40 or any(character not in "0123456789abcdef" for character in policy.commit):
        return "authorized AzzyAI commit policy is malformed"
    if policy.content_scope != "USER_AI":
        return "authorized AzzyAI content scope policy is malformed"
    if len(policy.expected_tree_sha256) != 64 or any(
        character not in "0123456789abcdef" for character in policy.expected_tree_sha256
    ):
        return "authorized AzzyAI tree identity policy is malformed"
    return None


def verify_azzyai_source(
    source_path: str | Path,
    *,
    observed_repository: str,
    observed_commit: str,
) -> Dict[str, object]:
    """Verify one extracted USER_AI tree against the reviewed source policy.

    The observed repository/commit are claims about how the human acquired the
    tree.  They are compared with the fixed project policy, while the tree
    identity is independently recomputed from the supplied bytes.  Neither the
    claims nor this descriptive result grants replacement authority.
    """

    policy = AUTHORIZED_AZZYAI_SOURCE
    result: Dict[str, object] = {
        "operation": "verify-azzyai-source",
        "artifact": "AzzyAI",
        "authorized_repository": policy.repository,
        "authorized_commit": policy.commit,
        "observed_repository": observed_repository,
        "observed_commit": observed_commit,
        "verification_method": "project-pinned USER_AI tree identity",
        "content_scope": policy.content_scope,
        "expected_tree_identity": policy.expected_tree_sha256,
        "observed_tree_identity": None,
        "source_claim_verified": False,
        "identity_verified": False,
        "content_verified": False,
        "signature_status": "not-verified",
        "provenance_claim": "immutable_source_identity_and_content_only",
        "result": "blocked",
        "reason": "not-run",
    }
    policy_error = _valid_source_policy(policy)
    if policy_error:
        result["reason"] = policy_error
        return result
    if observed_repository != policy.repository:
        result["reason"] = "observed AzzyAI repository does not match reviewed policy"
        return result
    if observed_commit != policy.commit:
        result["reason"] = "observed AzzyAI commit does not match reviewed policy"
        return result
    result["source_claim_verified"] = True
    try:
        observed_digest = source_tree_digest(source_path)
    except (OSError, RuntimeError, UnsupportedEntryError) as exc:
        result["reason"] = f"cannot verify AzzyAI USER_AI tree: {exc}"
        return result
    result["observed_tree_identity"] = observed_digest
    if observed_digest != policy.expected_tree_sha256:
        result["reason"] = "AzzyAI USER_AI tree does not match reviewed commit content"
        return result
    result.update(
        {
            "identity_verified": True,
            "content_verified": True,
            "result": "success",
            "reason": "AzzyAI repository, commit claim, and USER_AI content match reviewed policy",
        }
    )
    return result


def _compare_trees(source: Path, destination: Path) -> Dict[str, object]:
    try:
        source_snapshot = _snapshot_tree(source)
        destination_snapshot = _snapshot_tree(destination)
    except UnsupportedEntryError as exc:
        return {
            "status": "blocked",
            "missing": [],
            "extra": [],
            "mismatch": [],
            "reason": str(exc),
        }
    except OSError as exc:
        return {
            "status": "blocked",
            "missing": [],
            "extra": [],
            "mismatch": [],
            "reason": f"cannot compare USER_AI trees: {exc}",
        }

    source_keys = set(source_snapshot)
    destination_keys = set(destination_snapshot)
    missing = sorted(source_keys - destination_keys)
    extra = sorted(destination_keys - source_keys)
    mismatch = sorted(
        key
        for key in source_keys & destination_keys
        if source_snapshot[key] != destination_snapshot[key]
    )
    if missing or extra or mismatch:
        return {
            "status": "mismatch",
            "missing": missing,
            "extra": extra,
            "mismatch": mismatch,
            "reason": "source and destination USER_AI trees differ",
        }
    return {
        "status": "equal",
        "missing": [],
        "extra": [],
        "mismatch": [],
        "reason": "source and destination USER_AI trees are identical",
    }


def classify_user_ai(path: str | Path) -> Dict[str, object]:
    """Classify an existing USER_AI directory without mutating it."""

    root = Path(path)
    result: Dict[str, object] = {"path": str(root), "state": "missing"}
    try:
        if root.is_symlink():
            result.update({"state": "unsupported", "reason": "USER_AI symlink is unsupported"})
            return result
        if not root.exists():
            result["reason"] = "USER_AI directory is missing"
            return result
        if not root.is_dir():
            result.update({"state": "invalid", "reason": "USER_AI path is not a directory"})
            return result
        snapshot = _snapshot_tree(root)
    except PermissionError as exc:
        result.update({"state": "unreadable", "reason": f"USER_AI is unreadable: {exc}"})
        return result
    except UnsupportedEntryError as exc:
        result.update({"state": "unsupported", "reason": str(exc)})
        return result
    except OSError as exc:
        result.update({"state": "unreadable", "reason": str(exc)})
        return result

    if snapshot:
        result.update({"state": "populated", "reason": "USER_AI contains entries"})
    else:
        result.update({"state": "empty", "reason": "USER_AI directory exists but is empty"})
    return result


def _backup_result(source: Path, destination: Path) -> Dict[str, object]:
    return {
        "operation": "backup-azzyai-user-ai",
        "capability": "REVERSIBLE_MUTATION",
        "source": str(source),
        "destination": str(destination),
        "source_state": "unknown",
        "copy": {"status": "not-run", "success": False},
        "comparison": {"status": "not-run"},
        "backup_verified": False,
        "replacement_authorized": False,
        "mutation": False,
        "result": "blocked",
        "reason": "not-run",
    }


def _is_within(path: Path, root: Path) -> bool:
    path_real = path.resolve(strict=False)
    root_real = root.resolve(strict=False)
    return path_real == root_real or root_real in path_real.parents


def _paths_overlap(first: Path, second: Path) -> bool:
    return _is_within(first, second) or _is_within(second, first)


def _copy_tree(source: Path, destination: Path) -> None:
    # Preserve symlinks as entries so the independent snapshot rejects them;
    # never make the copy operation follow an untrusted link.
    shutil.copytree(source, destination, symlinks=True)


def backup_user_ai(
    source_path: str | Path,
    destination_path: str | Path,
    copy_fn: Optional[CopyFn] = None,
) -> Dict[str, object]:
    """Copy and independently verify an existing USER_AI tree."""

    source = Path(source_path)
    destination = Path(destination_path)
    result = _backup_result(source, destination)
    source_info = classify_user_ai(source)
    result["source_state"] = source_info["state"]
    if source_info["state"] not in ("empty", "populated"):
        result["reason"] = source_info.get("reason", "USER_AI source policy rejected")
        return result

    try:
        if _has_symlink_component(source) or _has_symlink_component(destination):
            result["reason"] = "source and backup paths must not contain symlink components"
            return result
        if _is_within(destination, source):
            result["reason"] = "backup destination is inside USER_AI"
            return result
    except (OSError, RuntimeError) as exc:
        result["reason"] = f"cannot resolve backup paths: {exc}"
        return result

    if destination.exists() or destination.is_symlink():
        result["reason"] = "backup destination already exists"
        return result

    copier = copy_fn or _copy_tree
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        parent_identity = _identity(destination.parent)
        copy_outcome = copier(source, destination)
        if _copy_failed(copy_outcome):
            raise RuntimeError("copy operation reported failure")
        if (
            _has_symlink_component(destination)
            or _identity(destination.parent) != parent_identity
        ):
            raise RuntimeError("backup destination parent changed during copy")
        result["mutation"] = True
        result["copy"] = {"status": "succeeded", "success": True}
    except Exception as exc:
        result["mutation"] = True
        result["copy"] = {"status": "failed", "success": False}
        result["reason"] = f"copy operation failed: {exc}"
        return result

    if not destination.exists() or not destination.is_dir() or destination.is_symlink():
        result["reason"] = "backup destination was not created as a regular directory"
        return result

    comparison = _compare_trees(source, destination)
    result["comparison"] = comparison
    if comparison["status"] != "equal":
        result["reason"] = comparison.get("reason", "backup comparison failed")
        return result

    result.update(
        {
            "backup_verified": True,
            "result": "success",
            "reason": "USER_AI copied and independently verified",
        }
    )
    return result


_AUTHORIZATION_MARKER = object()


@dataclass(frozen=True)
class ReplacementAuthorization:
    """Fresh, path-bound evidence consumed by ``replace_user_ai``."""

    source: Path
    destination: Path
    backup: Path
    source_snapshot: Tuple[Tuple[str, TreeEntry], ...]
    destination_snapshot: Tuple[Tuple[str, TreeEntry], ...]
    backup_snapshot: Tuple[Tuple[str, TreeEntry], ...]
    source_identity: Tuple[int, int]
    destination_identity: Tuple[int, int]
    destination_parent_identity: Tuple[int, int]
    backup_identity: Tuple[int, int]
    _marker: object


def _freeze_snapshot(snapshot: TreeSnapshot) -> Tuple[Tuple[str, TreeEntry], ...]:
    return tuple(sorted(snapshot.items()))


def authorize_user_ai_replacement(
    source_path: str | Path,
    destination_path: str | Path,
    backup_path: str | Path,
    copy_fn: Optional[CopyFn] = None,
    *,
    require_source_identity: bool = False,
) -> Tuple[Dict[str, object], Optional[ReplacementAuthorization]]:
    """Create replacement authority only after a fresh verified backup.

    The production CLI enables ``require_source_identity`` so the immutable
    AzzyAI policy is checked against the same source snapshot that is bound to
    the replacement authorization.  This closes the gap between a standalone
    preflight and F-07 authorization if the staged source is swapped in between.
    """

    source = Path(source_path)
    destination = Path(destination_path)
    backup = Path(backup_path)
    result: Dict[str, object] = {
        "operation": "authorize-azzyai-replacement",
        "capability": "REVERSIBLE_MUTATION",
        "source": str(source),
        "destination": str(destination),
        "backup": str(backup),
        "backup_verified": False,
        "replacement_authorized": False,
        "source_identity_verified": False,
        "source_tree_identity": None,
        "mutation": False,
        "result": "blocked",
        "reason": "not-run",
    }

    source_info = classify_user_ai(source)
    if source_info["state"] != "populated":
        result["reason"] = source_info.get("reason", "staged AzzyAI source must be populated")
        return result, None
    destination_info = classify_user_ai(destination)
    if destination_info["state"] not in ("empty", "populated"):
        result["reason"] = destination_info.get("reason", "existing USER_AI destination rejected")
        return result, None
    try:
        if _paths_overlap(source, destination):
            result["reason"] = "staged source and USER_AI destination overlap"
            return result, None
        if _paths_overlap(source, backup) or _paths_overlap(destination, backup):
            result["reason"] = "backup destination overlaps a USER_AI tree"
            return result, None
        if (
            _has_symlink_component(source)
            or _has_symlink_component(destination)
            or _has_symlink_component(backup)
        ):
            result["reason"] = "source, destination, and backup paths must not contain symlink components"
            return result, None
        source_snapshot = _snapshot_tree(source)
        if require_source_identity:
            policy = AUTHORIZED_AZZYAI_SOURCE
            policy_error = _valid_source_policy(policy)
            if policy_error:
                result["reason"] = policy_error
                return result, None
            source_digest = _tree_identity(source_snapshot)
            result["source_tree_identity"] = source_digest
            result["source_identity_verified"] = source_digest == policy.expected_tree_sha256
            if not result["source_identity_verified"]:
                result["reason"] = "staged AzzyAI source does not match reviewed commit content"
                return result, None
        destination_snapshot = _snapshot_tree(destination)
        source_identity = _identity(source)
        destination_identity = _identity(destination)
        destination_parent_identity = _identity(destination.parent)
    except (OSError, RuntimeError, UnsupportedEntryError) as exc:
        result["reason"] = f"cannot classify replacement trees: {exc}"
        return result, None

    backup_result = backup_user_ai(destination, backup, copy_fn=copy_fn)
    result["backup_verified"] = backup_result["backup_verified"]
    result["backup"] = backup_result
    result["mutation"] = backup_result["mutation"]
    if not backup_result["backup_verified"]:
        result["reason"] = backup_result.get("reason", "USER_AI backup was not verified")
        return result, None

    try:
        backup_snapshot = _snapshot_tree(backup)
        backup_identity = _identity(backup)
    except (OSError, RuntimeError, UnsupportedEntryError) as exc:
        result["reason"] = f"cannot bind verified backup evidence: {exc}"
        return result, None

    # The source and destination snapshots are bound to this one authorization;
    # later replacement revalidates both before any directory exchange.
    token = ReplacementAuthorization(
        source=source,
        destination=destination,
        backup=backup,
        source_snapshot=_freeze_snapshot(source_snapshot),
        destination_snapshot=_freeze_snapshot(destination_snapshot),
        backup_snapshot=_freeze_snapshot(backup_snapshot),
        source_identity=source_identity,
        destination_identity=destination_identity,
        destination_parent_identity=destination_parent_identity,
        backup_identity=backup_identity,
        _marker=_AUTHORIZATION_MARKER,
    )
    result.update(
        {
            "backup_verified": True,
            "replacement_authorized": True,
            "source_identity_verified": result["source_identity_verified"],
            "result": "success",
            "reason": "fresh USER_AI backup verified; replacement authorized for bound paths",
        }
    )
    return result, token


def _blocked_replacement(reason: str, *, authorization: bool = False) -> Dict[str, object]:
    return {
        "operation": "replace-azzyai-user-ai",
        "capability": "REVERSIBLE_MUTATION",
        "backup_verified": authorization,
        "replacement_authorized": False,
        "replacement_verified": False,
        "mutation": False,
        "result": "blocked",
        "reason": reason,
    }


def replace_user_ai(
    authorization: Optional[ReplacementAuthorization],
    copy_fn: Optional[CopyFn] = None,
    evidence_path: str | Path | None = None,
) -> Dict[str, object]:
    """Replace USER_AI only with fresh, path-bound authorization evidence."""

    if not isinstance(authorization, ReplacementAuthorization):
        return _blocked_replacement("replacement authorization is required")
    if authorization._marker is not _AUTHORIZATION_MARKER:
        return _blocked_replacement("replacement authorization marker is invalid")

    source = authorization.source
    destination = authorization.destination
    result: Dict[str, object] = {
        "operation": "replace-azzyai-user-ai",
        "capability": "REVERSIBLE_MUTATION",
        "source": str(source),
        "destination": str(destination),
        "backup": str(authorization.backup),
        "backup_verified": True,
        "replacement_authorized": True,
        "replacement_verified": False,
        "mutation": False,
        "result": "blocked",
        "reason": "not-run",
    }

    try:
        if _paths_overlap(source, destination):
            return _blocked_replacement("staged source and USER_AI destination overlap", authorization=True)
        if (
            _has_symlink_component(source)
            or _has_symlink_component(destination)
            or _has_symlink_component(authorization.backup)
        ):
            result["reason"] = "source, destination, and backup paths must not contain symlink components"
            return result
        if _identity(source) != authorization.source_identity:
            result["reason"] = "staged AzzyAI source identity changed after authorization"
            return result
        if _identity(destination) != authorization.destination_identity:
            result["reason"] = "USER_AI destination identity changed after authorization"
            return result
        if _identity(destination.parent) != authorization.destination_parent_identity:
            result["reason"] = "USER_AI destination parent changed after authorization"
            return result
        if _identity(authorization.backup) != authorization.backup_identity:
            result["reason"] = "verified USER_AI backup identity changed after authorization"
            return result
        source_now = _snapshot_tree(source)
        destination_now = _snapshot_tree(destination)
        backup_now = _snapshot_tree(authorization.backup)
    except (OSError, RuntimeError, UnsupportedEntryError) as exc:
        result["reason"] = f"cannot revalidate replacement trees: {exc}"
        return result

    if _freeze_snapshot(source_now) != authorization.source_snapshot:
        result["reason"] = "staged AzzyAI source changed after authorization"
        return result
    if _freeze_snapshot(destination_now) != authorization.destination_snapshot:
        result["reason"] = "USER_AI destination changed after backup authorization"
        return result
    if _freeze_snapshot(backup_now) != authorization.backup_snapshot:
        result["reason"] = "verified USER_AI backup changed after authorization"
        return result
    if backup_now != destination_now:
        result["reason"] = "verified USER_AI backup no longer matches destination"
        return result

    evidence = Path(evidence_path) if evidence_path is not None else None
    if evidence is not None and (
        _paths_overlap(evidence, source)
        or _paths_overlap(evidence, destination)
        or _paths_overlap(evidence, authorization.backup)
    ):
        result["reason"] = "evidence path must be outside USER_AI and its backup"
        return result

    staging = destination.parent / f".{destination.name}.azzyai-staging"
    previous = destination.parent / f".{destination.name}.azzyai-previous"
    if staging.exists() or staging.is_symlink():
        result["reason"] = "replacement staging path already exists"
        return result
    if previous.exists() or previous.is_symlink():
        result["reason"] = "replacement previous-state path already exists"
        return result

    copier = copy_fn or _copy_tree
    try:
        staging.parent.mkdir(parents=True, exist_ok=True)
        copy_outcome = copier(source, staging)
        result["mutation"] = True
        if _copy_failed(copy_outcome):
            raise RuntimeError("copy operation reported failure")
        result["copy"] = {"status": "succeeded", "success": True}
    except Exception as exc:
        result["copy"] = {"status": "failed", "success": False}
        try:
            _cleanup_staging(staging)
            result["staging_cleaned"] = True
        except OSError as cleanup_error:
            result["staging"] = str(staging)
            result["reason"] = f"replacement copy failed and staging cleanup failed; USER_AI was not changed: {cleanup_error}"
            return result
        result["reason"] = f"replacement copy failed; USER_AI was not changed: {exc}"
        return result

    comparison = _compare_trees(source, staging)
    result["comparison"] = comparison
    if comparison["status"] != "equal":
        try:
            _cleanup_staging(staging)
            result["staging_cleaned"] = True
        except OSError as cleanup_error:
            result["staging"] = str(staging)
            result["reason"] = f"replacement staging comparison failed and cleanup failed: {cleanup_error}"
            return result
        result["reason"] = comparison.get("reason", "replacement staging comparison failed")
        return result

    # The staging callback is a test seam for a copy command. Re-check every
    # bound path after it returns so a parent swap during the copy cannot turn
    # the subsequent rename into a mutation of an external tree.
    try:
        if (
            _has_symlink_component(source)
            or _has_symlink_component(destination)
            or _has_symlink_component(authorization.backup)
        ):
            raise RuntimeError("source, destination, or backup path changed to a symlink")
        if _identity(source) != authorization.source_identity:
            raise RuntimeError("staged AzzyAI source identity changed during copy")
        if _identity(destination) != authorization.destination_identity:
            raise RuntimeError("USER_AI destination identity changed during copy")
        if _identity(destination.parent) != authorization.destination_parent_identity:
            raise RuntimeError("USER_AI destination parent changed during copy")
        if _identity(authorization.backup) != authorization.backup_identity:
            raise RuntimeError("verified USER_AI backup identity changed during copy")
        source_after = _snapshot_tree(source)
        destination_after = _snapshot_tree(destination)
        backup_after = _snapshot_tree(authorization.backup)
    except (OSError, RuntimeError, UnsupportedEntryError) as exc:
        try:
            _cleanup_staging(staging)
            result["staging_cleaned"] = True
        except OSError as cleanup_error:
            result["staging"] = str(staging)
            result["reason"] = f"path revalidation failed and staging cleanup failed: {cleanup_error}"
            return result
        result["reason"] = f"path revalidation failed; USER_AI was not changed: {exc}"
        return result
    if (
        _freeze_snapshot(source_after) != authorization.source_snapshot
        or _freeze_snapshot(destination_after) != authorization.destination_snapshot
        or _freeze_snapshot(backup_after) != authorization.backup_snapshot
        or backup_after != destination_after
    ):
        try:
            _cleanup_staging(staging)
            result["staging_cleaned"] = True
        except OSError as cleanup_error:
            result["staging"] = str(staging)
            result["reason"] = f"path contents changed and staging cleanup failed: {cleanup_error}"
            return result
        result["reason"] = "bound source, destination, or backup contents changed; USER_AI was not changed"
        return result

    if evidence is not None:
        evidence_result = _append_evidence(
            evidence,
            {
                **result,
                "result": "authorized",
                "reason": "replacement authorized after fresh backup and exact staging comparison",
            },
            "replacement-authorized",
        )
        result["evidence"] = evidence_result
        if evidence_result["status"] != "succeeded":
            try:
                _cleanup_staging(staging)
                result["staging_cleaned"] = True
            except OSError as cleanup_error:
                result["reason"] = f"durable evidence failed and staging cleanup failed: {cleanup_error}"
                return result
            result["reason"] = "durable replacement evidence could not be persisted; USER_AI was not changed"
            return result

    try:
        destination.rename(previous)
        try:
            staging.rename(destination)
        except Exception:
            previous.rename(destination)
            raise
    except Exception as exc:
        result["reason"] = f"USER_AI directory exchange failed; original restored: {exc}"
        return result

    final_comparison = _compare_trees(source, destination)
    result["final_comparison"] = final_comparison
    if final_comparison["status"] != "equal":
        try:
            destination.rename(staging)
            previous.rename(destination)
        except Exception as exc:
            result["reason"] = f"replacement verification failed and restore failed: {exc}"
            result["staging"] = str(staging)
            result["previous"] = str(previous)
            return result
        result["staging"] = str(staging)
        result["reason"] = "replacement verification failed; original USER_AI restored"
        return result

    result.update(
        {
            "replacement_verified": True,
            "result": "success",
            "reason": "USER_AI replaced after verified backup and exact post-copy comparison",
            "previous": str(previous),
        }
    )
    if evidence is not None:
        completion_evidence = _append_evidence(evidence, result, "replacement-complete")
        result["evidence"] = completion_evidence
        if completion_evidence["status"] != "succeeded":
            try:
                destination.rename(staging)
                previous.rename(destination)
                restored = _compare_trees(authorization.backup, destination)["status"] == "equal"
                _cleanup_staging(staging)
            except Exception as exc:
                result.update(
                    {
                        "replacement_verified": False,
                        "result": "blocked",
                        "reason": (
                            "durable replacement completion evidence failed and original USER_AI "
                            f"restore failed: {exc}"
                        ),
                        "restored": False,
                    }
                )
                result["rollback_evidence"] = _append_evidence(
                    evidence, result, "replacement-rollback-failed"
                )
                return result
            result.update(
                {
                    "replacement_verified": False,
                    "result": "blocked",
                    "reason": (
                        "durable replacement completion evidence failed; original USER_AI "
                        "was restored"
                    ),
                    "restored": restored,
                }
            )
            result["rollback_evidence"] = _append_evidence(
                evidence, result, "replacement-rollback"
            )
    return result


def _emit(result: Dict[str, object]) -> int:
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("result") == "success" else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic AzzyAI USER_AI safety operations")
    subparsers = parser.add_subparsers(dest="area", required=True)
    backup = subparsers.add_parser("backup", help="backup and verify an existing USER_AI tree")
    backup.add_argument("--source", required=True)
    backup.add_argument("--destination", required=True)
    source_check = subparsers.add_parser(
        "verify-source",
        aliases=["source-check"],
        help="verify an extracted AzzyAI USER_AI tree against the reviewed commit policy",
    )
    source_check.add_argument("--source", required=True)
    source_check.add_argument("--source-repository", required=True)
    source_check.add_argument("--source-commit", required=True)
    policy = subparsers.add_parser(
        "source-policy",
        help="print the reviewed AzzyAI source identity used by verification",
    )
    policy.add_argument(
        "--field",
        choices=("repository", "commit", "content-scope", "tree-sha256"),
        help="print one policy value for use by a shell acquisition command",
    )
    replace = subparsers.add_parser("replace", help="backup, authorize, and safely replace USER_AI")
    replace.add_argument("--source", required=True, help="staged AzzyAI USER_AI directory")
    replace.add_argument("--source-repository", required=True, help="repository claimed for the staged source")
    replace.add_argument("--source-commit", required=True, help="full immutable commit claimed for the staged source")
    replace.add_argument("--destination", required=True, help="existing game USER_AI directory")
    replace.add_argument("--backup", required=True, help="external backup destination")
    replace.add_argument(
        "--evidence",
        help="optional external JSONL evidence path (default: <backup>.evidence.jsonl)",
    )
    args = parser.parse_args(argv)

    if args.area == "backup":
        result = backup_user_ai(args.source, args.destination)
        if result["result"] == "success":
            evidence_result = _append_evidence(
                Path(f"{args.destination}.evidence.jsonl"), result, "backup-complete"
            )
            result["evidence"] = evidence_result
            if evidence_result["status"] != "succeeded":
                result["result"] = "blocked"
                result["reason"] = "backup verified but durable evidence could not be persisted"
        return _emit(result)
    if args.area in ("verify-source", "source-check"):
        return _emit(
            verify_azzyai_source(
                args.source,
                observed_repository=args.source_repository,
                observed_commit=args.source_commit,
            )
        )
    if args.area == "source-policy":
        values = {
            "repository": AUTHORIZED_AZZYAI_SOURCE.repository,
            "commit": AUTHORIZED_AZZYAI_SOURCE.commit,
            "content_scope": AUTHORIZED_AZZYAI_SOURCE.content_scope,
            "expected_tree_sha256": AUTHORIZED_AZZYAI_SOURCE.expected_tree_sha256,
        }
        if args.field:
            field_keys = {
                "repository": "repository",
                "commit": "commit",
                "content-scope": "content_scope",
                "tree-sha256": "expected_tree_sha256",
            }
            print(values[field_keys[args.field]])
            return 0
        return _emit(
            {
                "operation": "azzyai-source-policy",
                "artifact": "AzzyAI",
                **values,
                "signature_status": "not-verified",
                "result": "success",
                "reason": "reviewed source identity policy",
            }
        )
    if args.area == "replace":
        source_verification = verify_azzyai_source(
            args.source,
            observed_repository=args.source_repository,
            observed_commit=args.source_commit,
        )
        if source_verification["result"] != "success":
            return _emit(source_verification)
        authorization_result, authorization = authorize_user_ai_replacement(
            args.source,
            args.destination,
            args.backup,
            require_source_identity=True,
        )
        if authorization is None:
            authorization_result["source_verification"] = source_verification
            return _emit(authorization_result)
        evidence_path = args.evidence or f"{args.backup}.evidence.jsonl"
        replacement_result = replace_user_ai(authorization, evidence_path=evidence_path)
        replacement_result["authorization"] = authorization_result
        replacement_result["source_verification"] = source_verification
        return _emit(replacement_result)
    parser.error("unsupported operation")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
