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
SCHEMA_VERSION = 2
INTERFACE_VERSION = 1
MANIFEST_NAME = "MANIFEST.json"
PYTHON_MINIMUM_VERSION = (3, 10, 0)
PYTHON_REQUIRED_MODULES = (
    "argparse",
    "hashlib",
    "json",
    "os",
    "pathlib",
    "shutil",
    "stat",
    "typing",
)
REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "canonical_source",
        "source_commit",
        "executor_sha256",
        "executor_relpath",
        "interface_version",
        "python",
    }
)
PYTHON_CONTRACT_KEYS = frozenset(
    {"invocation_path", "resolved_path", "version", "minimum_version"}
)
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")


class SettingsRuntimeError(Exception):
    """A deterministic build or verification failure."""


class SettingsRuntimeBuildError(SettingsRuntimeError):
    """The canonical source cannot be safely deployed."""


class SettingsRuntimeVerificationError(SettingsRuntimeError):
    """The deployed runtime artifact is invalid or incomplete."""


class PythonRuntimeError(SettingsRuntimeError):
    """The explicit Python interpreter does not satisfy the runtime contract."""


PYTHON_PROBE = r'''
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import sys
import typing

required = %r
for module_name in required:
    __import__(module_name)
print(json.dumps({
    "implementation": sys.implementation.name,
    "version": [sys.version_info.major, sys.version_info.minor, sys.version_info.micro],
    "executable": os.path.realpath(sys.executable),
}, sort_keys=True, separators=(",", ":")))
''' % (PYTHON_REQUIRED_MODULES,)


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


def _manifest(source_commit: str, executor_sha256: str, python_contract: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "canonical_source": CANONICAL_SOURCE,
        "executor_relpath": EXECUTOR_RELPATH,
        "executor_sha256": executor_sha256,
        "interface_version": INTERFACE_VERSION,
        "python": python_contract,
        "schema_version": SCHEMA_VERSION,
        "source_commit": source_commit,
    }


def _version_dict(version: tuple[int, int, int]) -> Dict[str, int]:
    return {"major": version[0], "minor": version[1], "micro": version[2]}


def _parse_version(value: Any, label: str) -> tuple[int, int, int]:
    if not isinstance(value, dict) or set(value) != {"major", "minor", "micro"}:
        raise PythonRuntimeError(f"{label} is malformed")
    parts = (value["major"], value["minor"], value["micro"])
    if any(type(part) is not int or part < 0 for part in parts):
        raise PythonRuntimeError(f"{label} is malformed")
    return parts


def _absolute_invocation_path(value: Any) -> Path:
    if not isinstance(value, str) or not value:
        raise PythonRuntimeError("interpreter invocation_path is malformed")
    path = Path(value)
    if not path.is_absolute():
        raise PythonRuntimeError("interpreter invocation_path must be absolute")
    return Path(os.path.abspath(path))


def _validate_interpreter_file(path: Path) -> Path:
    if not path.exists():
        raise PythonRuntimeError(f"interpreter is missing: {path}")
    if not path.is_file():
        raise PythonRuntimeError(f"interpreter is not a regular file: {path}")
    if not os.access(path, os.X_OK):
        raise PythonRuntimeError(f"interpreter is not executable: {path}")
    try:
        return path.resolve(strict=True)
    except OSError as exc:
        raise PythonRuntimeError(f"interpreter cannot be resolved: {exc}") from exc


def _probe_python(path: Path) -> Dict[str, Any]:
    try:
        completed = subprocess.run(
            [str(path), "-c", PYTHON_PROBE],
            check=True,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (FileNotFoundError, OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        raise PythonRuntimeError(f"interpreter probe failed: {exc}") from exc
    try:
        payload = json.loads(completed.stdout.strip())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PythonRuntimeError(f"interpreter probe returned malformed JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise PythonRuntimeError("interpreter probe did not return an object")
    required = {"implementation", "version", "executable"}
    if set(payload) != required:
        raise PythonRuntimeError("interpreter probe returned incomplete metadata")
    if not isinstance(payload["implementation"], str) or not payload["implementation"]:
        raise PythonRuntimeError("interpreter probe returned an invalid implementation")
    version = payload["version"]
    if not isinstance(version, list) or len(version) != 3 or any(type(part) is not int for part in version):
        raise PythonRuntimeError("interpreter probe returned a malformed version")
    executable = payload["executable"]
    if not isinstance(executable, str) or not Path(executable).is_absolute():
        raise PythonRuntimeError("interpreter probe returned an invalid executable path")
    return payload


def _ensure_supported_version(version: tuple[int, int, int]) -> None:
    if version[0] != 3:
        raise PythonRuntimeError("interpreter must be Python major version 3")
    if version < PYTHON_MINIMUM_VERSION:
        raise PythonRuntimeError("interpreter must be Python 3.10 or newer")


def _contract_from_interpreter(interpreter_path: str | os.PathLike[str]) -> Dict[str, Any]:
    invocation_path = _absolute_invocation_path(str(interpreter_path))
    resolved_path = _validate_interpreter_file(invocation_path)
    probe = _probe_python(invocation_path)
    version = tuple(probe["version"])
    _ensure_supported_version(version)
    return {
        "invocation_path": str(invocation_path),
        "resolved_path": str(resolved_path),
        "version": _version_dict(version),
        "minimum_version": _version_dict(PYTHON_MINIMUM_VERSION),
    }


def _validate_contract_metadata(contract: Any) -> tuple[Path, tuple[int, int, int], tuple[int, int, int]]:
    if not isinstance(contract, dict) or set(contract) != PYTHON_CONTRACT_KEYS:
        raise PythonRuntimeError("manifest Python contract is malformed")
    invocation_path = _absolute_invocation_path(contract["invocation_path"])
    resolved_path = contract["resolved_path"]
    if not isinstance(resolved_path, str) or not Path(resolved_path).is_absolute():
        raise PythonRuntimeError("manifest Python resolved_path is malformed")
    generation_version = _parse_version(contract["version"], "manifest Python version")
    minimum_version = _parse_version(contract["minimum_version"], "manifest Python minimum_version")
    if minimum_version != PYTHON_MINIMUM_VERSION:
        raise PythonRuntimeError("manifest Python minimum_version is unsupported")
    _ensure_supported_version(generation_version)
    return invocation_path, generation_version, minimum_version


def validate_python_runtime(contract: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the recorded interpreter without searching for a fallback."""

    invocation_path, _, minimum_version = _validate_contract_metadata(contract)
    resolved_path = _validate_interpreter_file(invocation_path)
    probe = _probe_python(invocation_path)
    observed_version = tuple(probe["version"])
    if observed_version[0] != minimum_version[0]:
        raise PythonRuntimeError("runtime interpreter has an unsupported major version")
    if observed_version < minimum_version:
        raise PythonRuntimeError("runtime interpreter is older than the supported minimum")
    return {
        "usable": True,
        "reason": "recorded Python interpreter satisfies the runtime contract",
        "invocation_path": str(invocation_path),
        "resolved_path_current": str(resolved_path),
        "observed_version": _version_dict(observed_version),
        "minimum_version": _version_dict(minimum_version),
        "implementation": probe["implementation"],
        "observed_executable": probe["executable"],
    }


def _manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    return (json.dumps(manifest, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def build_settings_runtime(
    repo_root: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    python_path: str | os.PathLike[str],
) -> Dict[str, Any]:
    """Copy the clean canonical executor and generate a deterministic manifest."""

    validated_root = _validated_repo_root(repo_root)
    source_commit = _source_commit(validated_root)
    source = _canonical_source(validated_root)
    source_bytes = _ensure_clean_canonical_source(validated_root, source, source_commit)
    executor_sha256 = hashlib.sha256(source_bytes).hexdigest()
    python_contract = _contract_from_interpreter(python_path)

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
    manifest = _manifest(source_commit, executor_sha256, python_contract)
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
    try:
        _validate_contract_metadata(manifest["python"])
    except PythonRuntimeError as exc:
        raise SettingsRuntimeVerificationError(str(exc)) from exc

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
        "python": manifest["python"],
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build or verify the bundled Settings executor runtime")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="copy the canonical executor and write MANIFEST.json")
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
            result = verify_settings_runtime(args.runtime_dir)
    except SettingsRuntimeError as exc:
        print(f"BLOCKED: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
