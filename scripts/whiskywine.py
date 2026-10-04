#!/usr/bin/env python3
"""Safely stage the manually sourced WhiskyWine runtime archive.

This helper does not establish runtime provenance or grant execution authority.
It only validates archive member types/paths and performs a bounded extraction
without allowing links or special files to escape the requested destination.
"""

from __future__ import annotations

import argparse
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


def _result(result: str, reason: str, *, mutation: bool = False) -> dict[str, Any]:
    return {
        "operation": "extract-whiskywine-runtime",
        "result": result,
        "reason": reason,
        "mutation": mutation,
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


def extract_runtime(archive_path: str | Path, destination_path: str | Path) -> dict[str, Any]:
    archive = Path(archive_path)
    destination = Path(destination_path)
    try:
        if destination.exists() and (destination.is_symlink() or not destination.is_dir()):
            return _result("blocked", "extraction destination must be a regular directory")
        descriptor = _archive_fd(archive)
    except (OSError, ValueError) as exc:
        return _result("blocked", f"cannot open runtime archive: {exc}")

    stage_path: Path | None = None
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

                destination.mkdir(parents=True, exist_ok=True)
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
                    for child in top_level:
                        final = destination / child.name
                        if final.exists() or final.is_symlink():
                            return _result("blocked", f"extraction destination already contains {child.name}")
                    for child in top_level:
                        os.replace(child, destination / child.name)
        return _result("success", "runtime archive validated and extracted safely", mutation=True)
    except (OSError, tarfile.TarError, ValueError) as exc:
        return _result("blocked", f"safe runtime extraction failed: {exc}")
    finally:
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
