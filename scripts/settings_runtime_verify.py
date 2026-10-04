#!/usr/bin/env python3
"""Verify a deployed uaRO Settings runtime bundle.

This module is intentionally self-contained so a copy can run from inside a
Settings.app bundle after the source repository is unavailable.  It verifies
deployment consistency only; it does not implement or authorize uaRO
operations.
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


CANONICAL_SOURCE = "scripts/uaro.py"
EXECUTOR_RELPATH = "uaro.py"
VERIFIER_RELPATH = "settings_runtime_verify.py"
SCHEMA_VERSION = 3
INTERFACE_VERSION = 1
MANIFEST_NAME = "MANIFEST.json"
PYTHON_MINIMUM_VERSION = (3, 10, 0)
PYTHON_REQUIRED_MODULES = (
    "argparse",
    "hashlib",
    "json",
    "os",
    "pathlib",
    "re",
    "shutil",
    "stat",
    "subprocess",
    "sys",
    "typing",
)
REQUIRED_MANIFEST_KEYS = frozenset(
    {
        "schema_version",
        "canonical_source",
        "source_commit",
        "executor_sha256",
        "executor_relpath",
        "verifier_sha256",
        "verifier_relpath",
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
    """A deterministic runtime verification failure."""


class SettingsRuntimeVerificationError(SettingsRuntimeError):
    """The deployed runtime artifact is invalid or incomplete."""


class PythonRuntimeError(SettingsRuntimeError):
    """The recorded Python interpreter does not satisfy the contract."""


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
    except (
        FileNotFoundError,
        OSError,
        UnicodeError,
        subprocess.CalledProcessError,
        subprocess.TimeoutExpired,
    ) as exc:
        raise PythonRuntimeError(f"interpreter probe failed: {exc}") from exc
    try:
        payload = json.loads(completed.stdout.strip())
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise PythonRuntimeError(f"interpreter probe returned malformed JSON: {exc}") from exc
    if not isinstance(payload, dict) or set(payload) != {"implementation", "version", "executable"}:
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


def contract_from_interpreter(interpreter_path: str | os.PathLike[str]) -> Dict[str, Any]:
    """Create generation metadata for an explicitly selected interpreter."""

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


def _validate_active_python() -> Dict[str, Any]:
    """Confirm the interpreter that is currently executing this verifier."""

    version = (sys.version_info.major, sys.version_info.minor, sys.version_info.micro)
    _ensure_supported_version(version)
    try:
        for module_name in PYTHON_REQUIRED_MODULES:
            __import__(module_name)
    except ImportError as exc:
        raise PythonRuntimeError(f"active interpreter is missing required standard library: {exc}") from exc
    return {
        "implementation": sys.implementation.name,
        "version": _version_dict(version),
        "executable": os.path.realpath(sys.executable),
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


def _validate_sha256(value: Any, label: str) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        raise SettingsRuntimeVerificationError(f"invalid {label} representation")
    return value


def _validate_regular_artifact(root: Path, relative_path: str, label: str) -> Path:
    path = root / relative_path
    if not path.is_file() or path.is_symlink():
        raise SettingsRuntimeVerificationError(f"deployed {label} is missing or not a regular file")
    return path


def _sha256_artifact(path: Path, label: str) -> str:
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except (OSError, UnicodeError) as exc:
        raise SettingsRuntimeVerificationError(f"deployed {label} cannot be read") from exc


def verify_settings_runtime(
    runtime_dir: str | os.PathLike[str],
    *,
    verify_python: bool = True,
) -> Dict[str, Any]:
    """Verify bundle identity and, optionally, execute its declared Python probe.

    ``verify_python=False`` is a static-only mode for callers that promise not
    to execute artifacts referenced by the bundle. It validates the Python
    contract's data shape but leaves interpreter usability UNCONFIRMED.
    """

    if type(verify_python) is not bool:
        raise SettingsRuntimeVerificationError("verify_python must be boolean")

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
    if manifest["verifier_relpath"] != VERIFIER_RELPATH:
        raise SettingsRuntimeVerificationError("unexpected verifier_relpath")
    source_commit = manifest["source_commit"]
    if not isinstance(source_commit, str) or not HEX40.fullmatch(source_commit):
        raise SettingsRuntimeVerificationError("invalid source_commit representation")
    expected_executor_digest = _validate_sha256(manifest["executor_sha256"], "executor_sha256")
    expected_verifier_digest = _validate_sha256(manifest["verifier_sha256"], "verifier_sha256")
    try:
        _validate_contract_metadata(manifest["python"])
    except PythonRuntimeError as exc:
        raise SettingsRuntimeVerificationError(str(exc)) from exc

    executor_path = _validate_regular_artifact(root, EXECUTOR_RELPATH, "uaro.py")
    actual_executor_digest = _sha256_artifact(executor_path, "executor")
    if actual_executor_digest != expected_executor_digest:
        raise SettingsRuntimeVerificationError("deployed executor digest mismatch")
    verifier_path = _validate_regular_artifact(root, VERIFIER_RELPATH, "settings_runtime_verify.py")
    actual_verifier_digest = _sha256_artifact(verifier_path, "runtime verifier")
    if actual_verifier_digest != expected_verifier_digest:
        raise SettingsRuntimeVerificationError("deployed verifier digest mismatch")

    if verify_python:
        try:
            active_python = _validate_active_python()
            python_evidence = validate_python_runtime(manifest["python"])
        except PythonRuntimeError as exc:
            raise SettingsRuntimeVerificationError(str(exc)) from exc
        python_evidence["active"] = active_python
        result = "PASS"
        python_verified = True
        python_status = "PASS"
        reason = "runtime artifact satisfies its deterministic contract"
    else:
        python_evidence = {
            "status": "UNCONFIRMED",
            "reason": "static-only mode does not execute the manifest interpreter",
            "declared_contract": manifest["python"],
        }
        result = "STRUCTURAL_PASS"
        python_verified = False
        python_status = "UNCONFIRMED"
        reason = "bundle files and metadata match; interpreter usability was not executed"
    return {
        "operation": "settings_runtime_verify",
        "runtime_dir": str(root),
        "schema_version": SCHEMA_VERSION,
        "interface_version": INTERFACE_VERSION,
        "executor_verified": True,
        "verifier_verified": True,
        "python_verified": python_verified,
        "python_status": python_status,
        "verification_scope": "full_runtime" if verify_python else "static_bundle",
        "result": result,
        "reason": reason,
        "executor_sha256": actual_executor_digest,
        "verifier_sha256": actual_verifier_digest,
        "python": python_evidence,
        "source_commit": source_commit,
    }


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify a bundled Settings runtime")
    parser.add_argument("runtime_dir", nargs="?", help="bundle-local runtime directory")
    parser.add_argument("--runtime-dir", dest="runtime_dir_option")
    args = parser.parse_args(argv)
    runtime_dir = args.runtime_dir_option or args.runtime_dir
    if not runtime_dir or (args.runtime_dir_option and args.runtime_dir):
        result = {
            "operation": "settings_runtime_verify",
            "result": "BLOCK",
            "reason": "exactly one runtime directory is required",
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 2
    try:
        result = verify_settings_runtime(runtime_dir)
    except SettingsRuntimeError as exc:
        result = {
            "operation": "settings_runtime_verify",
            "runtime_dir": str(Path(runtime_dir).expanduser()),
            "result": "BLOCK",
            "reason": str(exc),
        }
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 1
    print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
