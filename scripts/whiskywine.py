#!/usr/bin/env python3
"""Safely stage the manually sourced WhiskyWine runtime archive.

This helper does not establish runtime provenance or grant execution authority.
It only validates archive member types/paths and performs a bounded extraction
without allowing links or special files to escape the requested destination.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import shutil
import stat
import tarfile
import tempfile
from typing import Any
import unicodedata


def _result(
    result: str,
    reason: str,
    *,
    mutation: bool = False,
    lifecycle_state: str | None = None,
    post_state: str | None = None,
    rollback: str | None = None,
) -> dict[str, Any]:
    if lifecycle_state is None:
        lifecycle_state = "PUBLISHED_VERIFIED" if result == "success" else "BLOCKED_NO_MUTATION"
    if post_state is None:
        post_state = "PUBLISHED" if result == "success" else "UNCHANGED"
    if rollback is None:
        rollback = "not-needed"
    return {
        "operation": "extract-whiskywine-runtime",
        "result": result,
        "reason": reason,
        "mutation": mutation,
        "lifecycle_state": lifecycle_state,
        "post_state": post_state,
        "rollback": rollback,
    }


def _member_path(name: str) -> tuple[tuple[str, ...] | None, str | None]:
    path = PurePosixPath(name)
    if not name or path.is_absolute() or ".." in path.parts or "\\" in name:
        return None, "archive contains an absolute path, traversal, or backslash"
    parts = tuple(part for part in path.parts if part not in ("", "."))
    if not parts:
        return None, "archive contains an empty member path"
    return parts, None


def _archive_fd(path: Path) -> int:
    metadata = os.lstat(path)
    if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISREG(metadata.st_mode):
        raise OSError("runtime archive must be a regular file, not a symlink or special file")
    return os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))


def _is_symlink(path: Path) -> bool:
    try:
        return stat.S_ISLNK(os.lstat(path).st_mode)
    except OSError:
        return False


def _has_symlink_component(path: Path) -> bool:
    """Reject user path aliases while allowing stable macOS /var and /tmp aliases."""

    # Do not normalize away traversal before inspecting the user-supplied
    # components.  ``alias/../support`` can otherwise pass the check while the
    # kernel follows ``alias`` first and resolves the remainder elsewhere.
    if ".." in Path(path).parts:
        return True
    absolute = Path(os.path.abspath(path))
    current = Path(absolute.anchor)
    for component in absolute.parts[1:]:
        current /= component
        if _is_symlink(current):
            if current in (Path("/var"), Path("/tmp")) and os.path.realpath(current) in {
                "/private/var",
                "/private/tmp",
            }:
                continue
            return True
    return False


def _identity(path: Path) -> tuple[int, int]:
    metadata = os.lstat(path)
    return metadata.st_dev, metadata.st_ino


def _fd_identity(descriptor: int) -> tuple[int, int]:
    metadata = os.fstat(descriptor)
    return metadata.st_dev, metadata.st_ino


def _directory_fd(path: Path, *, dir_fd: int | None = None) -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return os.open(path, flags, dir_fd=dir_fd)


def _tree_manifest(root: Path) -> dict[str, tuple[str, int, str]]:
    """Capture regular-file bytes and directory shape for post-publish readback."""

    manifest: dict[str, tuple[str, int, str]] = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        metadata = os.lstat(item)
        if stat.S_ISLNK(metadata.st_mode):
            raise OSError("published runtime contains a symbolic link")
        if stat.S_ISDIR(metadata.st_mode):
            manifest[relative] = ("directory", 0, "")
            continue
        if not stat.S_ISREG(metadata.st_mode):
            raise OSError("published runtime contains a special file")
        digest = hashlib.sha256(item.read_bytes()).hexdigest()
        manifest[relative] = ("file", metadata.st_size, digest)
    return manifest


def extract_runtime(archive_path: str | Path, destination_path: str | Path) -> dict[str, Any]:
    archive = Path(archive_path)
    destination = Path(destination_path)
    parent_fd = -1
    try:
        if destination.name in ("", ".", ".."):
            return _result("blocked", "extraction destination must name a child directory")
        if _has_symlink_component(destination):
            return _result("blocked", "extraction destination contains a symlink path component")
        if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
            return _result("blocked", "extraction destination must be a regular directory")
        if not destination.parent.is_dir():
            return _result("blocked", "extraction destination parent is missing")
        parent_fd = _directory_fd(destination.parent)
        parent_identity = _fd_identity(parent_fd)
        descriptor = _archive_fd(archive)
    except (OSError, ValueError) as exc:
        if parent_fd != -1:
            os.close(parent_fd)
        return _result("blocked", f"cannot open runtime archive: {exc}")

    created_destination = False
    published = False
    destination_fd = -1
    stage_fd = -1
    try:
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            with tarfile.open(fileobj=stream, mode="r:*") as bundle:
                members = bundle.getmembers()
                seen: set[tuple[str, ...]] = set()
                normalized_seen: set[str] = set()
                kinds: dict[tuple[str, ...], str] = {}
                normalized_kinds: dict[str, str] = {}
                for member in members:
                    parts, member_error = _member_path(member.name)
                    if member_error:
                        return _result("blocked", member_error)
                    assert parts is not None
                    if parts in seen:
                        return _result("blocked", "archive contains duplicate member paths")
                    seen.add(parts)
                    normalized = "/".join(
                        unicodedata.normalize("NFC", part).casefold() for part in parts
                    )
                    if normalized in normalized_seen:
                        return _result("blocked", "archive contains colliding member paths")
                    normalized_seen.add(normalized)
                    if member.issym() or member.islnk():
                        return _result("blocked", "archive contains a symbolic or hard link")
                    if member.isdir():
                        kind = "directory"
                    elif member.isfile():
                        kind = "file"
                    else:
                        return _result("blocked", "archive contains a special file")
                    kinds[parts] = kind
                    normalized_kinds[normalized] = kind
                    for index in range(1, len(parts)):
                        parent = parts[:index]
                        if parent in kinds and kinds[parent] != "directory":
                            return _result("blocked", "archive contains a file/directory path collision")
                        normalized_parent = "/".join(
                            unicodedata.normalize("NFC", part).casefold() for part in parent
                        )
                        if normalized_parent in normalized_kinds and normalized_kinds[normalized_parent] != "directory":
                            return _result("blocked", "archive contains a file/directory path collision")

                with tempfile.TemporaryDirectory(prefix=".uaro-whiskywine-", dir=destination.parent) as stage:
                    stage_path = Path(stage)
                    for member in members:
                        parts, _ = _member_path(member.name)
                        assert parts is not None
                        target = stage_path.joinpath(*parts)
                        if member.isdir():
                            target.mkdir(parents=True, exist_ok=True)
                            continue
                        target.parent.mkdir(parents=True, exist_ok=True)
                        source = bundle.extractfile(member)
                        if source is None:
                            return _result("blocked", "archive member has no readable file body")
                        with source, target.open("xb") as output:
                            shutil.copyfileobj(source, output)
                        os.chmod(target, member.mode & 0o777)

                    top_level = list(stage_path.iterdir())
                    if {child.name for child in top_level} != {"Libraries"}:
                        return _result("blocked", "runtime archive must contain exactly one top-level Libraries directory")
                    staged_runtime = stage_path / "Libraries"
                    if not staged_runtime.is_dir() or staged_runtime.is_symlink():
                        return _result("blocked", "runtime archive Libraries root is not a regular directory")
                    expected_manifest = _tree_manifest(staged_runtime)
                    if _fd_identity(parent_fd) != parent_identity or _identity(destination.parent) != parent_identity:
                        return _result("blocked", "extraction destination parent changed before publish")
                    try:
                        destination_fd = _directory_fd(destination.name, dir_fd=parent_fd)
                    except FileNotFoundError:
                        os.mkdir(destination.name, mode=0o755, dir_fd=parent_fd)
                        created_destination = True
                        destination_fd = _directory_fd(destination.name, dir_fd=parent_fd)
                    except OSError as exc:
                        return _result("blocked", f"extraction destination is not a stable directory: {exc}")
                    if _fd_identity(parent_fd) != parent_identity or _identity(destination.parent) != parent_identity:
                        if created_destination:
                            try:
                                os.rmdir(destination.name, dir_fd=parent_fd)
                                created_destination = False
                                os.close(destination_fd)
                                destination_fd = -1
                            except OSError:
                                return _result(
                                    "blocked",
                                    "extraction destination parent changed after creation",
                                    mutation=True,
                                    lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                                    post_state="UNKNOWN",
                                    rollback="unknown",
                                )
                        return _result("blocked", "extraction destination parent changed before publish")
                    try:
                        os.stat("Libraries", dir_fd=destination_fd, follow_symlinks=False)
                    except FileNotFoundError:
                        pass
                    else:
                        return _result("blocked", "extraction destination already contains Libraries")
                    published_runtime = destination / "Libraries"
                    stage_fd = _directory_fd(stage_path)
                    try:
                        # Bind both sides of the rename to already-open
                        # directory descriptors. A path swap to a symlink or a
                        # different parent cannot redirect publication outside
                        # the validated destination.
                        os.replace(
                            "Libraries",
                            "Libraries",
                            src_dir_fd=stage_fd,
                            dst_dir_fd=destination_fd,
                        )
                    except OSError as exc:
                        if _fd_identity(destination_fd) == _identity(destination):
                            try:
                                os.stat("Libraries", dir_fd=destination_fd, follow_symlinks=False)
                                published_exists = True
                            except OSError:
                                published_exists = False
                        else:
                            published_exists = False
                        if published_exists and not published_runtime.is_symlink():
                            try:
                                observed_manifest = _tree_manifest(published_runtime)
                            except OSError:
                                observed_manifest = None
                            if (
                                observed_manifest == expected_manifest
                                and _fd_identity(parent_fd) == parent_identity
                                and _identity(destination.parent) == parent_identity
                                and _fd_identity(destination_fd) == _identity(destination)
                            ):
                                return _result(
                                    "success",
                                    "runtime publish completed despite a post-rename error",
                                    mutation=True,
                                )
                            return _result(
                                "blocked",
                                f"runtime publish outcome is ambiguous: {exc}",
                                mutation=True,
                                lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                                post_state="UNKNOWN",
                                rollback="unknown",
                            )
                        if created_destination and _fd_identity(destination_fd) == _identity(destination):
                            try:
                                os.rmdir(destination.name, dir_fd=parent_fd)
                            except OSError:
                                pass
                            else:
                                created_destination = False
                            return _result("blocked", f"runtime publish failed before mutation: {exc}")
                        return _result(
                            "blocked",
                            f"runtime publish outcome is ambiguous: {exc}",
                            mutation=created_destination,
                            lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                            post_state="UNKNOWN",
                            rollback="unknown",
                        )
                    published = True
                    if (
                        _fd_identity(parent_fd) != parent_identity
                        or _identity(destination.parent) != parent_identity
                        or _fd_identity(destination_fd) != _identity(destination)
                    ):
                        return _result(
                            "blocked",
                            "runtime publish parent changed during publication",
                            mutation=True,
                            lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                            post_state="UNKNOWN",
                            rollback="unknown",
                        )
                    observed_manifest = _tree_manifest(published_runtime)
                    if observed_manifest != expected_manifest:
                        return _result(
                            "blocked",
                            "runtime publish postcondition did not match staged content",
                            mutation=True,
                            lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                            post_state="UNKNOWN",
                            rollback="unknown",
                        )
        return _result("success", "runtime archive validated and published safely", mutation=True)
    except (OSError, tarfile.TarError, ValueError) as exc:
        if published:
            return _result(
                "blocked",
                f"runtime publish postcondition is ambiguous: {exc}",
                mutation=True,
                lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                post_state="UNKNOWN",
                rollback="unknown",
            )
        if created_destination and destination_fd != -1:
            try:
                if not os.listdir(destination_fd):
                    os.rmdir(destination.name, dir_fd=parent_fd)
                    created_destination = False
            except OSError:
                pass
        if created_destination:
            return _result(
                "blocked",
                f"runtime extraction outcome is ambiguous: {exc}",
                mutation=True,
                lifecycle_state="AMBIGUOUS_NEEDS_INSPECTION",
                post_state="UNKNOWN",
                rollback="unknown",
            )
        return _result("blocked", f"safe runtime extraction failed: {exc}")
    finally:
        for descriptor_to_close in (stage_fd, destination_fd, parent_fd):
            if descriptor_to_close != -1:
                try:
                    os.close(descriptor_to_close)
                except OSError:
                    pass
        if descriptor != -1:
            os.close(descriptor)


def _print(value: dict[str, Any]) -> int:
    print(json.dumps(value, sort_keys=True))
    return 0 if value["result"] == "success" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Safe WhiskyWine runtime archive extraction")
    sub = parser.add_subparsers(dest="command", required=True)
    extract = sub.add_parser("extract-runtime")
    extract.add_argument("--archive", required=True)
    extract.add_argument("--destination", required=True)
    args = parser.parse_args(argv)
    if args.command == "extract-runtime":
        return _print(extract_runtime(args.archive, args.destination))
    raise SystemExit(2)


if __name__ == "__main__":
    raise SystemExit(main())
