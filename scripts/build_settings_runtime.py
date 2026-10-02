#!/usr/bin/env python3
"""Build and verify the Settings bundled deterministic executor.

The canonical executor is ``scripts/uaro.py``.  This module only copies that
file and records a small deterministic deployment manifest; it does not contain
any command-specific executor implementation.

Deployment ordering contract:

    generate runtime resources
    -> verify runtime resources
    -> construct/finalize launcher
    -> codesign app bundle
    -> verify app signature
    -> deploy

Runtime verification is intentionally bundle-local.  The manifest records
deployment identity, not provenance or authorization.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Dict


EXPECTED_ORIGINS = frozenset(
    {
        "https://github.com/jirukouya/auRO-whisky-macOS-setup",
        "https://github.com/jirukouya/auRO-whisky-macOS-setup.git",
        "git@github.com:jirukouya/auRO-whisky-macOS-setup.git",
        "ssh://git@github.com/jirukouya/auRO-whisky-macOS-setup.git",
    }
)
CANONICAL_SOURCE = "scripts/uaro.py"
EXECUTOR_RELPATH = "uaro.py"
SCHEMA_VERSION = 1
INTERFACE_VERSION = 1
MANIFEST_NAME = "MANIFEST.json"
REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "canonical_source",
        "source_commit",
        "executor_sha256",
        "executor_relpath",
        "interface_version",
    }
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SettingsRuntimeError(Exception):
    """A deterministic build or verification failure."""


class SettingsRuntimeBuildError(SettingsRuntimeError):
    """The canonical source cannot be safely deployed."""


class SettingsRuntimeVerificationError(SettingsRuntimeError):
    """The deployed runtime artifact is invalid or incomplete."""


def _run_git(repo_root: Path, *args: str) -> str:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            check=True,
            capture_output=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", "") or str(exc)
        raise SettingsRuntimeBuildError(f"Git identity check failed: {detail.strip()}") from exc
    return completed.stdout.strip()


def _validated_repo_root(repo_root_arg: str | os.PathLike[str]) -> Path:
    requested = Path(repo_root_arg).expanduser()
    if not requested.exists() or not requested.is_dir():
        raise SettingsRuntimeBuildError(f"repository root is missing or not a directory: {requested}")
    try:
        repo_root = Path(_run_git(requested, "rev-parse", "--show-toplevel"))
    except SettingsRuntimeError:
        raise
    if not repo_root.is_absolute():
        repo_root = repo_root.resolve()
    origin = _run_git(repo_root, "config", "--get", "remote.origin.url")
    if origin not in EXPECTED_ORIGINS:
        raise SettingsRuntimeBuildError("repository origin is not the expected auRO repository")
    return repo_root


def _canonical_source(repo_root: Path) -> Path:
    source = repo_root / CANONICAL_SOURCE
    if not source.is_file() or source.is_symlink():
        raise SettingsRuntimeBuildError(f"canonical executor is missing or not a regular file: {source}")
    return source


def _committed_source(repo_root: Path, commit: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{CANONICAL_SOURCE}"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or str(exc)
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        raise SettingsRuntimeBuildError(f"cannot read committed canonical executor: {detail.strip()}") from exc
    return completed.stdout


def _ensure_clean_canonical_source(repo_root: Path, source: Path, commit: str) -> bytes:
    source_bytes = source.read_bytes()
    if source_bytes != _committed_source(repo_root, commit):
        raise SettingsRuntimeBuildError(
            "canonical scripts/uaro.py is dirty relative to HEAD; generation is blocked"
        )
    return source_bytes


def _source_commit(repo_root: Path) -> str:
    commit = _run_git(repo_root, "rev-parse", "HEAD")
    if not HEX40.fullmatch(commit):
        raise SettingsRuntimeBuildError("canonical HEAD is not a full 40-character commit id")
    return commit


def _manifest(source_commit: str, executor_sha256: str) -> Dict[str, Any]:
    return {
        "canonical_source": CANONICAL_SOURCE,
        "executor_relpath": EXECUTOR_RELPATH,
        "executor_sha256": executor_sha256,
        "interface_version": INTERFACE_VERSION,
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
    }


def _manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def build_settings_runtime(
    repo_root: str | os.PathLike[str],
    destination: str | os.PathLike[str],
) -> Dict[str, Any]:
    """Copy the clean canonical executor and generate a deterministic manifest."""

    validated_root = _validated_repo_root(repo_root)
    source_commit = _source_commit(validated_root)
    source = _canonical_source(validated_root)
    source_bytes = _ensure_clean_canonical_source(validated_root, source, source_commit)
    executor_sha256 = hashlib.sha256(source_bytes).hexdigest()

    runtime_dir = Path(destination).expanduser()
    if runtime_dir.exists() and runtime_dir.is_symlink():
        raise SettingsRuntimeBuildError("runtime destination must not be a symlink")
    try:
        runtime_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SettingsRuntimeBuildError(f"cannot create runtime destination: {exc}") from exc
    if not runtime_dir.is_dir():
        raise SettingsRuntimeBuildError(f"runtime destination is not a directory: {runtime_dir}")

    executor_path = runtime_dir / EXECUTOR_RELPATH
    manifest_path = runtime_dir / MANIFEST_NAME
    if executor_path.is_symlink() or manifest_path.is_symlink():
        raise SettingsRuntimeBuildError("runtime artifact paths must not be symlinks")
    try:
        executor_path.write_bytes(source_bytes)
        executor_path.chmod(source.stat().st_mode & 0o777)
    except OSError as exc:
        raise SettingsRuntimeBuildError(f"cannot write deployed executor: {exc}") from exc
    manifest = _manifest(source_commit, executor_sha256)
    try:
        manifest_path.write_bytes(_manifest_bytes(manifest))
    except OSError as exc:
        raise SettingsRuntimeBuildError(f"cannot write runtime manifest: {exc}") from exc
    return {
        "result": "success",
        "runtime_dir": str(runtime_dir),
        "executor": str(executor_path),
        "manifest": str(manifest_path),
        **manifest,
    }


def _load_manifest(runtime_dir: Path) -> Dict[str, Any]:
    manifest_path = runtime_dir / MANIFEST_NAME
    if not manifest_path.is_file() or manifest_path.is_symlink():
        raise SettingsRuntimeVerificationError("MANIFEST.json is missing or not a regular file")
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SettingsRuntimeVerificationError(f"MANIFEST.json is malformed: {exc}") from exc
    if not isinstance(payload, dict):
        raise SettingsRuntimeVerificationError("MANIFEST.json must contain an object")
    if set(payload) != REQUIRED_MANIFEST_KEYS:
        raise SettingsRuntimeVerificationError("MANIFEST.json has missing or unexpected fields")
    return payload


def verify_settings_runtime(runtime_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    """Verify the deployed runtime using only its executor and manifest."""

    root = Path(runtime_dir).expanduser()
    if not root.is_dir() or root.is_symlink():
        raise SettingsRuntimeVerificationError("runtime directory is missing or invalid")
    manifest = _load_manifest(root)
    if type(manifest["schema_version"]) is not int or manifest["schema_version"] != SCHEMA_VERSION:
        raise SettingsRuntimeVerificationError("unsupported manifest schema_version")
    if type(manifest["interface_version"]) is not int or manifest["interface_version"] != INTERFACE_VERSION:
        raise SettingsRuntimeVerificationError("unsupported executor interface_version")
    if manifest["canonical_source"] != CANONICAL_SOURCE:
        raise SettingsRuntimeVerificationError("unexpected canonical_source")
    if manifest["executor_relpath"] != EXECUTOR_RELPATH:
        raise SettingsRuntimeVerificationError("unexpected executor_relpath")
    source_commit = manifest["source_commit"]
    if not isinstance(source_commit, str) or not HEX40.fullmatch(source_commit):
        raise SettingsRuntimeVerificationError("invalid source_commit representation")
    expected_digest = manifest["executor_sha256"]
    if not isinstance(expected_digest, str) or not HEX64.fullmatch(expected_digest):
        raise SettingsRuntimeVerificationError("invalid executor_sha256 representation")

    executor_path = root / EXECUTOR_RELPATH
    if not executor_path.is_file() or executor_path.is_symlink():
        raise SettingsRuntimeVerificationError("deployed uaro.py is missing or not a regular file")
    actual_digest = hashlib.sha256(executor_path.read_bytes()).hexdigest()
    if actual_digest != expected_digest:
        raise SettingsRuntimeVerificationError("deployed executor digest mismatch")
    return {
        "result": "success",
        "runtime_dir": str(root),
        "executor_relpath": EXECUTOR_RELPATH,
        "executor_sha256": actual_digest,
        "source_commit": source_commit,
        "schema_version": SCHEMA_VERSION,
        "interface_version": INTERFACE_VERSION,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the bundled Settings executor runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="copy the canonical executor and write MANIFEST.json")
    build.add_argument("--repo-root", required=True)
    build.add_argument("--destination", required=True)
    verify = subparsers.add_parser("verify", help="verify a generated runtime without its source repository")
    verify.add_argument("--runtime-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_settings_runtime(args.repo_root, args.destination)
        else:
            result = verify_settings_runtime(args.runtime_dir)
    except SettingsRuntimeError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
