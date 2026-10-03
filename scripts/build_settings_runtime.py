#!/usr/bin/env python3
"""Build a deterministic uaRO Settings runtime bundle.

Generation is repository-side. Verification is authoritative in
``settings_runtime_verify.py`` so the copied verifier can run after the
source repository is unavailable.

Deployment ordering contract:

    generate runtime resources
    -> verify runtime resources
    -> construct/finalize launcher
    -> codesign app bundle
    -> verify app signature
    -> deploy

This module does not contain uaRO command implementations or a second runtime
verification algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
from typing import Any, Dict

import settings_runtime_verify as verifier


EXPECTED_ORIGINS = frozenset(
    {
        "https://github.com/jirukouya/auRO-whisky-macOS-setup",
        "https://github.com/jirukouya/auRO-whisky-macOS-setup.git",
        "git@github.com:jirukouya/auRO-whisky-macOS-setup.git",
        "ssh://git@github.com/jirukouya/auRO-whisky-macOS-setup.git",
    }
)
CANONICAL_SOURCE = verifier.CANONICAL_SOURCE
EXECUTOR_RELPATH = verifier.EXECUTOR_RELPATH
VERIFIER_RELPATH = verifier.VERIFIER_RELPATH
VERIFIER_SOURCE = "scripts/settings_runtime_verify.py"
SCHEMA_VERSION = verifier.SCHEMA_VERSION
INTERFACE_VERSION = verifier.INTERFACE_VERSION
MANIFEST_NAME = verifier.MANIFEST_NAME
PYTHON_MINIMUM_VERSION = verifier.PYTHON_MINIMUM_VERSION
PYTHON_REQUIRED_MODULES = verifier.PYTHON_REQUIRED_MODULES
REQUIRED_MANIFEST_KEYS = verifier.REQUIRED_MANIFEST_KEYS
PYTHON_CONTRACT_KEYS = verifier.PYTHON_CONTRACT_KEYS
HEX40 = re.compile(r"^[0-9a-f]{40}$")

SettingsRuntimeError = verifier.SettingsRuntimeError
SettingsRuntimeVerificationError = verifier.SettingsRuntimeVerificationError
PythonRuntimeError = verifier.PythonRuntimeError
validate_python_runtime = verifier.validate_python_runtime


class SettingsRuntimeBuildError(SettingsRuntimeError):
    """The canonical source cannot be safely deployed."""


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
    repo_root = Path(_run_git(requested, "rev-parse", "--show-toplevel"))
    if not repo_root.is_absolute():
        repo_root = repo_root.resolve()
    origin = _run_git(repo_root, "config", "--get", "remote.origin.url")
    if origin not in EXPECTED_ORIGINS:
        raise SettingsRuntimeBuildError("repository origin is not the expected auRO repository")
    return repo_root


def _canonical_source(repo_root: Path, relative_path: str, label: str) -> Path:
    source = repo_root / relative_path
    if not source.is_file() or source.is_symlink():
        raise SettingsRuntimeBuildError(f"canonical {label} is missing or not a regular file: {source}")
    return source


def _committed_source(repo_root: Path, commit: str, relative_path: str, label: str) -> bytes:
    try:
        completed = subprocess.run(
            ["git", "-C", str(repo_root), "show", f"{commit}:{relative_path}"],
            check=True,
            capture_output=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        detail = getattr(exc, "stderr", b"") or str(exc)
        if isinstance(detail, bytes):
            detail = detail.decode(errors="replace")
        raise SettingsRuntimeBuildError(f"cannot read committed canonical {label}: {detail.strip()}") from exc
    return completed.stdout


def _ensure_clean_canonical_source(
    repo_root: Path, source: Path, commit: str, relative_path: str, label: str
) -> bytes:
    source_bytes = source.read_bytes()
    if source_bytes != _committed_source(repo_root, commit, relative_path, label):
        raise SettingsRuntimeBuildError(f"canonical {relative_path} is dirty relative to HEAD; generation is blocked")
    return source_bytes


def _source_commit(repo_root: Path) -> str:
    commit = _run_git(repo_root, "rev-parse", "HEAD")
    if not HEX40.fullmatch(commit):
        raise SettingsRuntimeBuildError("canonical HEAD is not a full 40-character commit id")
    return commit


def _manifest(
    source_commit: str,
    executor_sha256: str,
    verifier_sha256: str,
    python_contract: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "canonical_source": CANONICAL_SOURCE,
        "executor_relpath": EXECUTOR_RELPATH,
        "executor_sha256": executor_sha256,
        "interface_version": INTERFACE_VERSION,
        "python": python_contract,
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
        "verifier_relpath": VERIFIER_RELPATH,
        "verifier_sha256": verifier_sha256,
    }


def _manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_artifact(path: Path, data: bytes, mode: int, label: str) -> None:
    try:
        path.write_bytes(data)
        path.chmod(mode & 0o777)
    except OSError as exc:
        raise SettingsRuntimeBuildError(f"cannot write deployed {label}: {exc}") from exc


def build_settings_runtime(
    repo_root: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    python_path: str | os.PathLike[str],
) -> Dict[str, Any]:
    """Build, verify, and atomically publish a complete runtime bundle."""

    validated_root = _validated_repo_root(repo_root)
    source_commit = _source_commit(validated_root)
    executor_source = _canonical_source(validated_root, CANONICAL_SOURCE, "executor")
    verifier_source = _canonical_source(validated_root, VERIFIER_SOURCE, "runtime verifier")

    # Both deployed sources are checked before any destination is created.
    executor_bytes = _ensure_clean_canonical_source(
        validated_root, executor_source, source_commit, CANONICAL_SOURCE, "executor"
    )
    verifier_bytes = _ensure_clean_canonical_source(
        validated_root, verifier_source, source_commit, VERIFIER_SOURCE, "runtime verifier"
    )
    python_contract = verifier.contract_from_interpreter(python_path)
    manifest = _manifest(
        source_commit,
        hashlib.sha256(executor_bytes).hexdigest(),
        hashlib.sha256(verifier_bytes).hexdigest(),
        python_contract,
    )

    runtime_dir = Path(destination).expanduser()
    if runtime_dir.exists() or runtime_dir.is_symlink():
        raise SettingsRuntimeBuildError("runtime destination already exists; refusing to replace it")
    parent = runtime_dir.parent
    try:
        parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise SettingsRuntimeBuildError(f"cannot create runtime destination parent: {exc}") from exc
    if not parent.is_dir() or parent.is_symlink():
        raise SettingsRuntimeBuildError("runtime destination parent is invalid")

    temporary_dir = Path(tempfile.mkdtemp(prefix=f".{runtime_dir.name}.", dir=str(parent)))
    try:
        _write_artifact(
            temporary_dir / EXECUTOR_RELPATH,
            executor_bytes,
            executor_source.stat().st_mode,
            "executor",
        )
        _write_artifact(
            temporary_dir / VERIFIER_RELPATH,
            verifier_bytes,
            verifier_source.stat().st_mode,
            "runtime verifier",
        )
        _write_artifact(
            temporary_dir / MANIFEST_NAME,
            _manifest_bytes(manifest),
            0o644,
            "runtime manifest",
        )
        try:
            verification = verifier.verify_settings_runtime(temporary_dir)
        except SettingsRuntimeError as exc:
            raise SettingsRuntimeBuildError(f"generated runtime verification failed: {exc}") from exc
        if not isinstance(verification, dict) or verification.get("result") != "PASS":
            raise SettingsRuntimeBuildError("generated runtime verification did not return PASS")
        try:
            os.replace(str(temporary_dir), str(runtime_dir))
        except OSError as exc:
            raise SettingsRuntimeBuildError(f"cannot publish generated runtime atomically: {exc}") from exc
    except Exception:
        shutil.rmtree(temporary_dir, ignore_errors=True)
        raise

    return {
        "result": "success",
        "runtime_dir": str(runtime_dir),
        "executor": str(runtime_dir / EXECUTOR_RELPATH),
        "verifier": str(runtime_dir / VERIFIER_RELPATH),
        "manifest": str(runtime_dir / MANIFEST_NAME),
        **manifest,
    }


def verify_settings_runtime(runtime_dir: str | os.PathLike[str]) -> Dict[str, Any]:
    """Compatibility export of the canonical bundle-local verifier."""

    return verifier.verify_settings_runtime(runtime_dir)


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the bundled Settings executor runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="copy canonical runtime sources and write MANIFEST.json")
    build.add_argument("--repo-root", required=True)
    build.add_argument("--destination", required=True)
    build.add_argument("--python", dest="python_path", required=True)
    verify = subparsers.add_parser("verify", help="verify a generated runtime without its source repository")
    verify.add_argument("--runtime-dir", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "build":
            result = build_settings_runtime(args.repo_root, args.destination, args.python_path)
        else:
            result = verifier.verify_settings_runtime(args.runtime_dir)
    except SettingsRuntimeError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
