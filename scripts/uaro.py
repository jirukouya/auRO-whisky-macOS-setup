#!/usr/bin/env python3
"""Small deterministic uaRO execution primitives.

This module contains the Phase 2A FCOM transaction, savedata backup, and
explicit-path structural/health inspection. It intentionally does not discover
uaRO paths or perform installation, repair, launcher, or uninstall work.
"""

from __future__ import annotations

import argparse
import ctypes
import ctypes.util
import json
import hashlib
import os
from pathlib import Path
import shutil
import stat
import sys
import tempfile
from typing import Callable, Dict, Optional, Tuple


SITE_A_OFFSET = 0x2C0CD
SITE_B_OFFSET = 0x21E39
A_UNPATCHED = bytes.fromhex("dc")
A_PATCHED = bytes.fromhex("d8")
B_UNPATCHED = bytes.fromhex("dcd8dfe0")
B_PATCHED = bytes.fromhex("ddd8b440")
EXPECTED_CHANGED_OFFSETS = {
    SITE_A_OFFSET,
    SITE_B_OFFSET,
    SITE_B_OFFSET + 2,
    SITE_B_OFFSET + 3,
}


class UnsupportedEntryError(Exception):
    """A filesystem entry cannot be compared safely by this spike."""


def _site_state(data: bytes, offset: int, unpatched: bytes, patched: bytes) -> str:
    value = data[offset : offset + len(unpatched)]
    if len(value) != len(unpatched):
        return "truncated"
    if value == unpatched:
        return "unpatched"
    if value == patched:
        return "patched"
    return "unknown"


def _whole_state(site_a: str, site_b: str) -> str:
    if "truncated" in (site_a, site_b):
        return "TRUNCATED"
    if "unknown" in (site_a, site_b):
        return "UNKNOWN"
    if site_a != site_b:
        return "MIXED"
    return "PATCHED" if site_a == "patched" else "UNPATCHED"


def _target_record(target: Path, operation: str) -> Dict[str, object]:
    capability = "READ" if operation == "fcom-check" else "REVERSIBLE_MUTATION"
    return {
        "operation": operation,
        "capability": capability,
        "target": str(target),
        "backup": str(target.with_name(target.name + ".orig-backup")),
        "mutation": False,
        "backup_created": False,
        "backup_status": "not-verified",
        "rollback": "not-run",
        "verification": "not-run",
    }


def _read_and_classify(target: Path, operation: str) -> Tuple[Dict[str, object], Optional[bytes]]:
    result = _target_record(target, operation)
    symlink_reason = _symlink_path_reason(target)
    if symlink_reason:
        return _blocked(result, symlink_reason), None
    try:
        data = target.read_bytes()
    except OSError as exc:
        result.update(
            {
                "site_a": "unavailable",
                "site_b": "unavailable",
                "state": "UNKNOWN",
                "pre_state": "UNKNOWN",
                "post_state": "UNKNOWN",
                "result": "blocked",
                "reason": f"cannot read target: {exc}",
            }
        )
        return result, None

    site_a = _site_state(data, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED)
    site_b = _site_state(data, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED)
    state = _whole_state(site_a, site_b)
    result.update(
        {
            "site_a": site_a,
            "site_b": site_b,
            "state": state,
            "pre_state": state,
            "post_state": state,
        }
    )
    return result, data


def check_fcom(target_path: str | Path) -> Dict[str, object]:
    """Read and classify an explicit target without any filesystem writes."""

    target = Path(target_path)
    result, data = _read_and_classify(target, "fcom-check")
    if data is not None:
        result.update({"result": "success", "reason": "classified"})
    return result


def _blocked(result: Dict[str, object], reason: str) -> Dict[str, object]:
    result.update(
        {
            "result": "blocked",
            "reason": reason,
            "verification": "not-run",
        }
    )
    result.setdefault("state", "UNKNOWN")
    result.setdefault("pre_state", "UNKNOWN")
    result.setdefault("post_state", "UNKNOWN")
    return result


def _validate_backup(backup_bytes: bytes, original: bytes) -> Optional[str]:
    if len(backup_bytes) != len(original):
        return "existing original backup has a different size"
    if _site_state(backup_bytes, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED) != "unpatched":
        return "existing original backup does not contain unpatched Site A bytes"
    if _site_state(backup_bytes, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED) != "unpatched":
        return "existing original backup does not contain unpatched Site B bytes"
    return None


def _fd_identity(fd: int) -> Tuple[int, int]:
    metadata = os.fstat(fd)
    return metadata.st_dev, metadata.st_ino


def _path_identity(target: Path) -> Tuple[int, int]:
    metadata = os.lstat(target)
    return metadata.st_dev, metadata.st_ino


def _symlink_path_reason(target: Path) -> Optional[str]:
    """Reject a symlink at the explicit mutation target itself.

    Parent paths may include platform aliases such as macOS's ``/var`` link;
    the target is protected independently by ``O_NOFOLLOW`` and lstat-based
    identity checks so a replacement race cannot redirect the write.
    """

    try:
        metadata = os.lstat(target)
    except FileNotFoundError:
        return None
    except OSError as exc:
        return f"cannot inspect target path: {exc}"
    if stat.S_ISLNK(metadata.st_mode):
        return f"symlink path component is unsupported: {target}"
    return None


def _read_fd(fd: int) -> bytes:
    os.lseek(fd, 0, os.SEEK_SET)
    chunks = []
    while True:
        chunk = os.read(fd, 1024 * 1024)
        if not chunk:
            return b"".join(chunks)
        chunks.append(chunk)


def _precondition_error(
    target: Path,
    fd: int,
    expected_identity: Tuple[int, int],
    expected_bytes: bytes,
) -> Optional[str]:
    try:
        if _fd_identity(fd) != expected_identity or _path_identity(target) != expected_identity:
            return "TARGET_REPLACED: setup.exe identity changed during validation"
        current = _read_fd(fd)
    except OSError as exc:
        return f"TARGET_CHANGED: cannot revalidate setup.exe before mutation: {exc}"
    if current != expected_bytes:
        return "TARGET_CHANGED: setup.exe bytes changed after initial classification"
    return None


def _backup_precondition_error(
    backup: Path,
    fd: int,
    expected_identity: Tuple[int, int],
    expected_bytes: bytes,
) -> Optional[str]:
    try:
        if _fd_identity(fd) != expected_identity or _path_identity(backup) != expected_identity:
            return "BACKUP_REPLACED: original backup identity changed before mutation"
        current = _read_fd(fd)
    except OSError as exc:
        return f"BACKUP_CHANGED: cannot revalidate original backup before mutation: {exc}"
    if current != expected_bytes:
        return "BACKUP_CHANGED: original backup bytes changed before mutation"
    return None


def _create_backup_from_snapshot(backup: Path, original: bytes) -> None:
    with backup.open("xb") as stream:
        stream.write(original)
        stream.flush()
        os.fsync(stream.fileno())


def _open_readonly_regular(path: Path) -> int:
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError("backup is not a regular file")
        return fd
    except Exception:
        os.close(fd)
        raise


def _write_fd(fd: int, data: bytes) -> None:
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    written = 0
    while written < len(data):
        written += os.write(fd, data[written:])
    os.fsync(fd)


def _rename_exchange(source: Path, target: Path) -> None:
    """Atomically exchange two existing paths on macOS."""

    if sys.platform != "darwin":
        raise RuntimeError("atomic exchange is only available on macOS")
    try:
        library = ctypes.CDLL(ctypes.util.find_library("c") or None, use_errno=True)
        renameatx_np = library.renameatx_np
    except (OSError, AttributeError) as exc:
        raise RuntimeError(f"macOS atomic exchange unavailable: {exc}") from exc
    renameatx_np.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    renameatx_np.restype = ctypes.c_int
    at_fdcwd = -2
    rename_swap = 0x00000002
    if renameatx_np(at_fdcwd, os.fsencode(source), at_fdcwd, os.fsencode(target), rename_swap) != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error))


def _publish_staged_target(
    temporary: Path,
    target: Path,
    expected_identity: Tuple[int, int],
    expected_bytes: bytes,
) -> Tuple[int, int]:
    """Publish a staged target and reject a macOS path-replacement race."""

    if sys.platform != "darwin":
        os.replace(temporary, target)
        return _path_identity(target)
    _rename_exchange(temporary, target)
    old_target_fd: Optional[int] = None
    try:
        old_target_fd = _open_readonly_regular(temporary)
        old_target_bytes = _read_fd(old_target_fd)
    finally:
        if old_target_fd is not None:
            os.close(old_target_fd)
    if _path_identity(temporary) != expected_identity:
        _rename_exchange(temporary, target)
        raise RuntimeError("TARGET_REPLACED: setup.exe identity changed during atomic publish")
    if old_target_bytes != expected_bytes:
        _rename_exchange(temporary, target)
        raise RuntimeError("TARGET_CHANGED: setup.exe bytes changed during atomic publish")
    published_identity = _path_identity(target)
    temporary.unlink()
    return published_identity


def _write_atomic_fcom_target(
    target: Path,
    expected_identity: Tuple[int, int],
    original: bytes,
    patched: bytes,
    read_fd: int,
) -> Tuple[int, int]:
    """Stage patched bytes beside the target and atomically publish them.

    A failed stage leaves the original target untouched. The target and its
    original snapshot are rechecked immediately before replacement so a stale
    read cannot silently overwrite a same-path change.
    """

    temporary: Optional[Path] = None
    try:
        mode = stat.S_IMODE(os.fstat(read_fd).st_mode)
        with tempfile.NamedTemporaryFile(
            mode="w+b", prefix=f".{target.name}.", dir=target.parent, delete=False
        ) as stream:
            temporary = Path(stream.name)
            _write_fd(stream.fileno(), patched)
            os.fchmod(stream.fileno(), mode)
        reason = _precondition_error(target, read_fd, expected_identity, original)
        if reason:
            raise RuntimeError(reason)
        if os.fstat(read_fd).st_nlink > 1:
            raise RuntimeError("TARGET_LINKED: hard-linked setup.exe is unsupported for atomic replacement")
        try:
            published_identity = _publish_staged_target(
                temporary, target, expected_identity, original
            )
        except (OSError, RuntimeError):
            # After exchange/rename has started, the path may no longer contain
            # the staged inode. Leave it for explicit inspection rather than
            # risking deletion of a concurrent replacement.
            temporary = None
            raise
        temporary = None
        return published_identity
    finally:
        if temporary is not None:
            try:
                temporary.unlink()
            except FileNotFoundError:
                pass


def _backup_postcondition_error(
    backup: Path,
    fd: int,
    expected_identity: Tuple[int, int],
    expected_bytes: bytes,
) -> Optional[str]:
    """Prove the original backup was not replaced or changed during the transaction."""

    try:
        if _fd_identity(fd) != expected_identity or _path_identity(backup) != expected_identity:
            return "BACKUP_REPLACED: original backup identity changed during mutation"
        if _read_fd(fd) != expected_bytes:
            return "BACKUP_CHANGED: original backup bytes changed during mutation"
    except OSError as exc:
        return f"BACKUP_CHANGED: cannot verify original backup after mutation: {exc}"
    return None


def _record_post_state(result: Dict[str, object], data: bytes) -> None:
    """Record the bytes actually present after a mutation attempt."""

    site_a = _site_state(data, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED)
    site_b = _site_state(data, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED)
    result.update({"site_a": site_a, "site_b": site_b, "post_state": _whole_state(site_a, site_b)})


def _record_current_target_state(result: Dict[str, object], target: Path) -> None:
    """Read the current target path without following a target symlink."""

    fd: Optional[int] = None
    try:
        fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise RuntimeError("target is not a regular file")
        _record_post_state(result, _read_fd(fd))
    except (OSError, RuntimeError):
        result.update({"site_a": "unavailable", "site_b": "unavailable", "post_state": "UNKNOWN"})
    finally:
        if fd is not None:
            os.close(fd)

def apply_fcom(
    target_path: str | Path,
    before_mutation_hook: Optional[Callable[[], None]] = None,
) -> Dict[str, object]:
    """Apply the approved two-site transaction to an explicit target.

    The optional hook is an internal deterministic test seam. It runs after
    backup validation/creation and before the final precondition check; the CLI
    never exposes or uses it.
    """

    target = Path(target_path)
    result = _target_record(target, "fcom-apply")
    read_fd: Optional[int] = None
    backup_fd: Optional[int] = None
    try:
        symlink_reason = _symlink_path_reason(target)
        if symlink_reason:
            return _blocked(result, symlink_reason)
        try:
            read_fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            if not stat.S_ISREG(os.fstat(read_fd).st_mode):
                raise RuntimeError("target is not a regular file")
            expected_identity = _fd_identity(read_fd)
            original = _read_fd(read_fd)
            if _path_identity(target) != expected_identity:
                return _blocked(result, "TARGET_REPLACED: setup.exe identity changed during classification")
        except (OSError, RuntimeError) as exc:
            result.update(
                {
                    "site_a": "unavailable",
                    "site_b": "unavailable",
                    "state": "UNKNOWN",
                    "pre_state": "UNKNOWN",
                    "post_state": "UNKNOWN",
                    "result": "blocked",
                    "reason": f"cannot read target: {exc}",
                }
            )
            return result

        site_a = _site_state(original, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED)
        site_b = _site_state(original, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED)
        state = _whole_state(site_a, site_b)
        result.update(
            {
                "site_a": site_a,
                "site_b": site_b,
                "state": state,
                "pre_state": state,
                "post_state": state,
            }
        )

        if state == "PATCHED":
            result.update({"result": "success", "reason": "already patched; no-op"})
            return result
        if state != "UNPATCHED":
            return _blocked(result, f"FCOM state {state} is not patchable")

        backup = target.with_name(target.name + ".orig-backup")
        backup_symlink_reason = _symlink_path_reason(backup)
        if backup_symlink_reason:
            return _blocked(result, backup_symlink_reason)
        try:
            if backup.exists():
                backup_fd = _open_readonly_regular(backup)
                backup_identity = _fd_identity(backup_fd)
                if _path_identity(backup) != backup_identity:
                    return _blocked(result, "BACKUP_REPLACED: original backup identity changed during validation")
                backup_bytes = _read_fd(backup_fd)
                backup_error = _validate_backup(backup_bytes, original)
                if backup_error:
                    return _blocked(result, backup_error)
            else:
                _create_backup_from_snapshot(backup, original)
                result["backup_created"] = True
                backup_fd = _open_readonly_regular(backup)
                backup_identity = _fd_identity(backup_fd)
                if _path_identity(backup) != backup_identity:
                    return _blocked(result, "BACKUP_REPLACED: original backup identity changed during creation")
                backup_bytes = _read_fd(backup_fd)
                if backup_bytes != original:
                    return _blocked(result, "new original backup does not exactly match target")
        except (OSError, RuntimeError) as exc:
            return _blocked(result, f"cannot validate/create original backup: {exc}")

        if before_mutation_hook is not None:
            try:
                before_mutation_hook()
            except Exception as exc:
                return _blocked(result, f"TARGET_CHANGED: pre-mutation hook failed: {exc}")

        reason = _backup_precondition_error(backup, backup_fd, backup_identity, original)
        if reason:
            return _blocked(result, reason)
        reason = _precondition_error(target, read_fd, expected_identity, original)
        if reason:
            return _blocked(result, reason)

        patched = bytearray(original)
        patched[SITE_A_OFFSET : SITE_A_OFFSET + 1] = A_PATCHED
        patched[SITE_B_OFFSET : SITE_B_OFFSET + 4] = B_PATCHED
        try:
            published_identity = _write_atomic_fcom_target(
                target, expected_identity, original, bytes(patched), read_fd
            )
        except (OSError, RuntimeError) as exc:
            _record_current_target_state(result, target)
            if result.get("post_state") == "PATCHED":
                result["mutation"] = True
                return _blocked(result, f"FCOM patch publish outcome requires inspection: {exc}")
            result["rollback"] = "not-needed"
            return _blocked(result, f"FCOM patch staging/publish failed: {exc}")

        result["mutation"] = True
        final_fd: Optional[int] = None
        try:
            final_fd = os.open(target, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            if not stat.S_ISREG(os.fstat(final_fd).st_mode):
                raise RuntimeError("target is not a regular file after publish")
            if _fd_identity(final_fd) != published_identity:
                raise RuntimeError("TARGET_REPLACED: setup.exe identity changed after atomic publish")
            final = _read_fd(final_fd)
            if _fd_identity(final_fd) != published_identity or _path_identity(target) != published_identity:
                raise RuntimeError("TARGET_REPLACED: setup.exe identity changed during post-publish read")
        except (OSError, RuntimeError) as exc:
            _record_current_target_state(result, target)
            return _blocked(result, f"FCOM patch post-publish read failed: {exc}")
        finally:
            if final_fd is not None:
                os.close(final_fd)

        _record_post_state(result, final)
        if final != bytes(patched):
            return _blocked(result, "TARGET_CHANGED: setup.exe changed after atomic publish")
        if _site_state(final, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED) != "patched":
            return _blocked(result, "Site A final bytes are not patched")
        if _site_state(final, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED) != "patched":
            return _blocked(result, "Site B final bytes are not patched")
        if len(final) != len(original):
            return _blocked(result, "FCOM patch changed target size")

        expected = bytearray(original)
        expected[SITE_A_OFFSET : SITE_A_OFFSET + 1] = A_PATCHED
        expected[SITE_B_OFFSET : SITE_B_OFFSET + 4] = B_PATCHED
        if final != bytes(expected):
            return _blocked(result, "FCOM patch changed bytes outside approved sites")
        changed_offsets = {
            index for index, (before, after) in enumerate(zip(original, final)) if before != after
        }
        if changed_offsets != EXPECTED_CHANGED_OFFSETS:
            return _blocked(result, "FCOM patch diff is not exactly the approved byte set")

        backup_error = _backup_postcondition_error(backup, backup_fd, backup_identity, original)
        if backup_error:
            result["backup_status"] = "blocked"
            return _blocked(result, backup_error)

        result.update(
            {
                "post_state": "PATCHED",
                "backup_status": "verified",
                "result": "success",
                "reason": "patched and verified",
                "verification": "passed",
            }
        )
        return result
    finally:
        if backup_fd is not None:
            os.close(backup_fd)
        if read_fd is not None:
            os.close(read_fd)

def _snapshot_tree(root: Path) -> Dict[str, Tuple[str, int, str]]:
    """Return a deterministic tree snapshot, rejecting unsupported entries."""

    entries: Dict[str, Tuple[str, int, str]] = {}

    def visit(directory: Path, relative: Path) -> None:
        try:
            children = sorted(os.scandir(directory), key=lambda entry: entry.name)
        except OSError as exc:
            raise OSError(f"cannot read {directory}: {exc}") from exc
        for entry in children:
            child_relative = relative / entry.name
            key = child_relative.as_posix()
            try:
                if entry.is_symlink():
                    raise UnsupportedEntryError(f"symbolic link is unsupported: {key}")
                if entry.is_dir(follow_symlinks=False):
                    entries[key] = ("directory", 0, "")
                    visit(Path(entry.path), child_relative)
                elif entry.is_file(follow_symlinks=False):
                    digest = hashlib.sha256()
                    size = 0
                    with open(entry.path, "rb") as stream:
                        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                            digest.update(chunk)
                            size += len(chunk)
                    entries[key] = ("file", size, digest.hexdigest())
                else:
                    raise UnsupportedEntryError(f"unsupported filesystem entry: {key}")
            except OSError as exc:
                raise OSError(f"cannot inspect {entry.path}: {exc}") from exc

    visit(root, Path("."))
    return entries


def classify_savedata(source_path: str | Path) -> Dict[str, object]:
    """Classify an explicit savedata directory without writing to it."""

    source = Path(source_path)
    result: Dict[str, object] = {"path": str(source), "state": "missing"}
    try:
        if source.is_symlink():
            result.update({"state": "unsupported", "reason": "savedata symlink is unsupported"})
            return result
        if not source.exists():
            result["reason"] = "savedata directory is missing"
            return result
        if not source.is_dir():
            result.update({"state": "invalid", "reason": "savedata path is not a directory"})
            return result
        snapshot = _snapshot_tree(source)
    except PermissionError as exc:
        result.update({"state": "unreadable", "reason": f"savedata is unreadable: {exc}"})
        return result
    except UnsupportedEntryError as exc:
        result.update({"state": "unsupported", "reason": str(exc)})
        return result
    except OSError as exc:
        result.update({"state": "unreadable", "reason": str(exc)})
        return result

    if snapshot:
        result.update({"state": "populated", "reason": "savedata contains entries"})
    else:
        result.update({"state": "empty", "reason": "savedata directory exists but is empty"})
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
            "reason": f"cannot compare backup trees: {exc}",
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
            "reason": "source and destination trees differ",
        }
    return {
        "status": "equal",
        "missing": [],
        "extra": [],
        "mismatch": [],
        "reason": "source and destination trees are identical",
    }


def _backup_result(game_dir: Path, source: Path, destination: Path) -> Dict[str, object]:
    return {
        "operation": "backup-savedata",
        "capability": "REVERSIBLE_MUTATION",
        "game_dir": str(game_dir),
        "source": str(source),
        "destination": str(destination),
        "source_state": "unknown",
        "copy": {"status": "not-run", "success": False},
        "comparison": {"status": "not-run"},
        "backup_verified": False,
        "deletion_authority": False,
        "mutation": False,
        "result": "blocked",
        "reason": "not-run",
    }


def _destination_inside_game(game_dir: Path, destination: Path) -> bool:
    game_real = game_dir.resolve(strict=False)
    destination_real = destination.resolve(strict=False)
    return destination_real == game_real or game_real in destination_real.parents


def _copy_savedata(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination)


def backup_savedata(
    game_dir_path: str | Path,
    destination_path: str | Path,
    copy_fn: Optional[Callable[[Path, Path], object]] = None,
) -> Dict[str, object]:
    """Create and independently verify a savedata backup.

    ``copy_fn`` is an internal test seam.  The CLI always uses the standard
    copytree implementation; tests can model partial copies and failed copy
    statuses against this same production transaction.
    """

    game_dir = Path(game_dir_path)
    source = game_dir / "savedata"
    destination = Path(destination_path)
    result = _backup_result(game_dir, source, destination)
    source_info = classify_savedata(source)
    result["source_state"] = source_info["state"]
    if source_info["state"] not in ("empty", "populated"):
        result["reason"] = source_info.get("reason", "savedata source policy rejected")
        return result

    try:
        if _destination_inside_game(game_dir, destination):
            result["reason"] = "backup destination is inside GAME_DIR"
            return result
    except (OSError, RuntimeError) as exc:
        result["reason"] = f"cannot resolve backup paths: {exc}"
        return result

    if destination.exists() or destination.is_symlink():
        result["reason"] = "backup destination already exists"
        return result

    copier = copy_fn or _copy_savedata
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        copy_outcome = copier(source, destination)
        if copy_outcome is False:
            raise RuntimeError("copy operation reported failure")
        result["mutation"] = True
        result["copy"] = {"status": "succeeded", "success": True}
    except Exception as exc:
        result["mutation"] = True
        result["copy"] = {"status": "failed", "success": False}
        result["reason"] = f"copy operation failed: {exc}"
        return result

    if not destination.exists() or not destination.is_dir():
        result["reason"] = "backup destination was not created as a directory"
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
            "reason": "backup copied and independently verified",
        }
    )
    return result


def inspect_install(
    game_dir_path: str | Path,
    apps_dir_path: Optional[str | Path] = None,
) -> Dict[str, object]:
    """Inspect only explicitly supplied paths and never mutate them."""

    game_dir = Path(game_dir_path)
    setup = game_dir / "setup.exe"
    savedata = game_dir / "savedata"
    fcom = check_fcom(setup)
    evidence: Dict[str, object] = {
        "game_dir_exists": game_dir.is_dir(),
        "uaro_exe_exists": (game_dir / "uaRO.exe").is_file(),
        "setup_exe_exists": setup.is_file(),
        "fcom": {
            "state": fcom.get("state", "UNKNOWN"),
            "site_a": fcom.get("site_a", "unavailable"),
            "site_b": fcom.get("site_b", "unavailable"),
            "result": fcom.get("result", "blocked"),
            "reason": fcom.get("reason", "not observed"),
        },
        "savedata": classify_savedata(savedata),
        "optioninfo_lua_exists": (savedata / "OptionInfo.lua").is_file(),
        "dinput_ini_exists": (game_dir / "dinput.ini").is_file(),
    }

    if apps_dir_path is None:
        apps: Optional[Dict[str, object]] = None
    else:
        apps_dir = Path(apps_dir_path)
        apps = {}
        for name, required in (
            ("UaRO Patcher.app", True),
            ("UaRO Settings.app", True),
            ("UaRO Game.app", False),
        ):
            apps[name] = {
                "exists": (apps_dir / name).is_dir(),
                "required": required,
                "structural_only": True,
            }

    return {
        "operation": "inspect",
        "capability": "READ",
        "game_dir": str(game_dir),
        "apps_dir": str(apps_dir_path) if apps_dir_path is not None else None,
        "evidence": evidence,
        "apps": apps,
        "evidence_scope": "explicit structural facts only",
        "execution": "UNCONFIRMED",
        "mutation": False,
        "deletion_authority": False,
        "result": "success",
        "reason": "inspection completed without mutation",
    }


def _doctor_path_state(
    path_value: Optional[str | Path],
    label: str,
    *,
    required: bool,
) -> Dict[str, object]:
    """Classify one explicitly supplied directory without following a root symlink."""

    if path_value is None:
        return {
            "state": "UNKNOWN",
            "path": None,
            "reason": f"{label} was not supplied",
            "required": required,
        }
    path = Path(path_value).expanduser()
    if path.is_symlink():
        return {
            "state": "BLOCKED",
            "path": str(path),
            "reason": f"{label} must not be a symlink",
            "required": required,
        }
    if not path.exists():
        return {
            "state": "BLOCKED" if required else "UNKNOWN",
            "path": str(path),
            "reason": f"{label} is missing",
            "required": required,
        }
    if not path.is_dir():
        return {
            "state": "BLOCKED",
            "path": str(path),
            "reason": f"{label} is not a directory",
            "required": required,
        }
    return {
        "state": "PASS",
        "path": str(path),
        "reason": f"{label} is an explicit regular directory",
        "required": required,
    }


def _doctor_regular_file_state(path: Path, label: str) -> Dict[str, object]:
    if path.is_symlink():
        return {"state": "BLOCKED", "path": str(path), "reason": f"{label} must not be a symlink"}
    if not path.exists():
        return {"state": "BLOCKED", "path": str(path), "reason": f"{label} is missing"}
    if not path.is_file():
        return {"state": "BLOCKED", "path": str(path), "reason": f"{label} is not a regular file"}
    return {"state": "PASS", "path": str(path), "reason": f"{label} is present"}


def _doctor_fcom_state(fcom: Dict[str, object]) -> Dict[str, object]:
    observed = fcom.get("state", "UNKNOWN")
    if observed == "PATCHED" and fcom.get("result") == "success":
        state = "PASS"
        reason = "FCOM sites are classified as PATCHED"
    elif observed == "UNPATCHED" and fcom.get("result") == "success":
        state = "BLOCKED"
        reason = "FCOM sites are unpatched; repair remains a separate mutation route"
    else:
        state = "BLOCKED"
        reason = f"FCOM evidence is not a safe healthy state: {observed}"
    return {
        "state": state,
        "observed_state": observed,
        "reason": reason,
        "evidence": fcom,
    }


def _doctor_settings_runtime_state(runtime_dir: Optional[str | Path]) -> Dict[str, object]:
    if runtime_dir is None:
        return {
            "state": "UNKNOWN",
            "path": None,
            "reason": "Settings runtime directory was not supplied",
        }
    path_state = _doctor_path_state(runtime_dir, "Settings runtime directory", required=True)
    if path_state["state"] != "PASS":
        return path_state
    try:
        from settings_runtime_verify import SettingsRuntimeError, verify_settings_runtime

        evidence = verify_settings_runtime(path_state["path"], verify_python=False)
    except ImportError as exc:
        return {
            "state": "BLOCKED",
            "path": path_state["path"],
            "reason": f"Settings runtime verifier is unavailable: {exc}",
        }
    except SettingsRuntimeError as exc:
        return {
            "state": "BLOCKED",
            "path": path_state["path"],
            "reason": str(exc),
        }
    return {
        "state": "PASS" if evidence.get("result") == "STRUCTURAL_PASS" else "BLOCKED",
        "path": path_state["path"],
        "python_runtime": "UNCONFIRMED",
        "reason": "Settings bundle files and metadata match; declared Python was not executed",
        "evidence": evidence,
    }


def doctor_install(
    game_dir_path: str | Path,
    apps_dir_path: Optional[str | Path] = None,
    settings_runtime_dir: Optional[str | Path] = None,
) -> Dict[str, object]:
    """Aggregate explicit structural facts without mutation or implicit discovery.

    A PASS result means only that the requested structural checks passed. Live
    execution, game behavior, and patch freshness remain explicitly unknown.
    """

    game_state = _doctor_path_state(game_dir_path, "game directory", required=True)
    checks: Dict[str, object] = {
        "game_directory": game_state,
        "freshness": {
            "state": "UNKNOWN",
            "reason": "No authoritative server patch-cycle or local freshness signal was supplied",
        },
    }
    if game_state["state"] == "PASS":
        game_dir = Path(game_state["path"])
        inspection = inspect_install(game_dir, apps_dir_path)
        core_files = {
            "uaro_exe": _doctor_regular_file_state(game_dir / "uaRO.exe", "uaRO.exe"),
            "setup_exe": _doctor_regular_file_state(game_dir / "setup.exe", "setup.exe"),
        }
        checks["core_files"] = core_files
        checks["fcom"] = _doctor_fcom_state(inspection["evidence"]["fcom"])
        savedata_evidence = inspection["evidence"]["savedata"]
        savedata_state = savedata_evidence["state"]
        checks["savedata"] = {
            "state": (
                "PASS"
                if savedata_state in ("empty", "populated")
                else "BLOCKED"
                if savedata_state == "unsupported"
                else "UNKNOWN"
            ),
            "evidence": savedata_evidence,
            "reason": "savedata directory is readable; absence is not treated as zero data",
        }
    else:
        checks.update(
            {
                "core_files": {"state": "BLOCKED", "reason": "game directory is unavailable"},
                "fcom": {"state": "BLOCKED", "reason": "game directory is unavailable"},
                "savedata": {"state": "UNKNOWN", "reason": "game directory is unavailable"},
            }
        )

    if apps_dir_path is None:
        checks["launchers"] = _doctor_path_state(None, "launcher directory", required=False)
    else:
        apps_state = _doctor_path_state(apps_dir_path, "launcher directory", required=True)
        if apps_state["state"] == "PASS":
            apps = inspect_install(game_dir_path, apps_dir_path)["apps"]
            required_names = ("UaRO Patcher.app", "UaRO Settings.app")
            launcher_checks = {
                name: {
                    "state": (
                        "PASS"
                        if apps[name]["exists"] and not (Path(apps_dir_path) / name).is_symlink()
                        else "BLOCKED"
                    ),
                    "exists": apps[name]["exists"],
                    "required": apps[name]["required"],
                }
                for name in required_names
            }
            optional = apps["UaRO Game.app"]
            launcher_checks["UaRO Game.app"] = {
                "state": (
                    "PASS"
                    if optional["exists"] and not (Path(apps_dir_path) / "UaRO Game.app").is_symlink()
                    else "UNKNOWN"
                ),
                "exists": optional["exists"],
                "required": False,
            }
            checks["launchers"] = {
                "state": (
                    "PASS"
                    if all(
                        item["state"] == "PASS"
                        for name, item in launcher_checks.items()
                        if name != "UaRO Game.app"
                    )
                    else "BLOCKED"
                ),
                "path": str(apps_dir_path),
                "evidence": launcher_checks,
            }
        else:
            checks["launchers"] = apps_state

    checks["settings_runtime"] = _doctor_settings_runtime_state(settings_runtime_dir)
    blocking = []
    for name, value in checks.items():
        if isinstance(value, dict) and value.get("state") == "BLOCKED":
            blocking.append(name)
        elif name == "core_files" and isinstance(value, dict):
            if any(item.get("state") == "BLOCKED" for item in value.values() if isinstance(item, dict)):
                blocking.append(name)
    result = "blocked" if blocking else "success"
    return {
        "operation": "doctor",
        "capability": "READ",
        "game_dir": str(game_dir_path),
        "apps_dir": str(apps_dir_path) if apps_dir_path is not None else None,
        "settings_runtime_dir": str(settings_runtime_dir) if settings_runtime_dir is not None else None,
        "checks": checks,
        "overall_state": "BLOCKED" if blocking else "PASS",
        "evidence_scope": "explicit structural and local-artifact facts only",
        "execution": "UNCONFIRMED",
        "behavior": "UNCONFIRMED",
        "mutation": False,
        "deletion_authority": False,
        "result": result,
        "reason": (
            "; ".join(f"blocked: {name}" for name in blocking)
            if blocking
            else "requested structural checks passed; live claims remain unconfirmed"
        ),
    }


def _emit(result: Dict[str, object]) -> int:
    print(json.dumps(result, sort_keys=True))
    return 0 if result.get("result") == "success" else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministic uaRO FCOM spike")
    subparsers = parser.add_subparsers(dest="area", required=True)
    fcom = subparsers.add_parser("fcom", help="FCOM classification and patch transaction")
    fcom_subparsers = fcom.add_subparsers(dest="operation", required=True)
    check = fcom_subparsers.add_parser("check", help="classify without writing")
    check.add_argument("target")
    apply = fcom_subparsers.add_parser("apply", help="apply and verify the two-site patch")
    apply.add_argument("target")
    backup = subparsers.add_parser("backup", help="deterministic backup operations")
    backup_subparsers = backup.add_subparsers(dest="backup_operation", required=True)
    savedata = backup_subparsers.add_parser("savedata", help="copy and verify savedata")
    savedata.add_argument("--game-dir", required=True)
    savedata.add_argument("--destination", required=True)
    inspect = subparsers.add_parser("inspect", help="inspect explicit paths without mutation")
    inspect.add_argument("--game-dir", required=True)
    inspect.add_argument("--apps-dir")
    doctor = subparsers.add_parser("doctor", help="aggregate explicit health facts without mutation")
    doctor.add_argument("--game-dir", required=True)
    doctor.add_argument("--apps-dir")
    doctor.add_argument("--settings-runtime-dir")
    args = parser.parse_args(argv)

    if args.area == "fcom" and args.operation == "check":
        return _emit(check_fcom(args.target))
    if args.area == "fcom" and args.operation == "apply":
        return _emit(apply_fcom(args.target))
    if args.area == "backup" and args.backup_operation == "savedata":
        return _emit(backup_savedata(args.game_dir, args.destination))
    if args.area == "inspect":
        return _emit(inspect_install(args.game_dir, args.apps_dir))
    if args.area == "doctor":
        return _emit(doctor_install(args.game_dir, args.apps_dir, args.settings_runtime_dir))
    parser.error("unsupported operation")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
