#!/usr/bin/env python3
"""Verify the fixed Whisky.app release identity used by uaRO.

This module checks facts about a downloaded archive.  It does not download,
install, remove quarantine, or grant execution authority.  Its
``verify-and-extract`` command only extracts into a caller-provided temporary
directory after verifying the same immutable archive snapshot.  The expected
digest is a project policy value copied from official Homebrew cask metadata
for Whisky 2.3.5; a candidate archive cannot supply or replace it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
from pathlib import PurePosixPath
import stat
import subprocess
import tempfile
from typing import Any, Dict, Optional
import unicodedata
import zipfile


WHISKY_VERSION = "2.3.5"
WHISKY_REPOSITORY = "https://github.com/IsaacMarovitz/Whisky"
WHISKY_RELEASE_TAG = f"v{WHISKY_VERSION}"
WHISKY_OFFICIAL_SOURCE = "https://github.com/IsaacMarovitz/Whisky/releases/download/v2.3.5/Whisky.zip"
WHISKY_PROJECT_FALLBACK_SOURCE = "https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/Whisky-app-2.3.5.zip"
# Official Homebrew cask metadata, reviewed 2026-10-03.
WHISKY_EXPECTED_SHA256 = "62fce6aa7034cc84e4809a35cb46af37e7932368102450dd2b3d4a18cbc7b94e"
WHISKY_POLICY_ANCHOR = "https://raw.githubusercontent.com/Homebrew/homebrew-cask/87180be1e381499a994990a044944580d180be44/Casks/w/whisky.rb"


class WhiskyPolicyError(ValueError):
    """The fixed Whisky trust policy is malformed."""



def _policy_error() -> Optional[str]:
    if WHISKY_VERSION != "2.3.5":
        return "authorized Whisky version policy is malformed"
    if WHISKY_RELEASE_TAG != "v2.3.5":
        return "authorized Whisky release tag policy is malformed"
    if WHISKY_REPOSITORY != "https://github.com/IsaacMarovitz/Whisky":
        return "authorized Whisky repository policy is malformed"
    if WHISKY_OFFICIAL_SOURCE != "https://github.com/IsaacMarovitz/Whisky/releases/download/v2.3.5/Whisky.zip":
        return "authorized Whisky official source policy is malformed"
    if WHISKY_PROJECT_FALLBACK_SOURCE != "https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/Whisky-app-2.3.5.zip":
        return "authorized Whisky fallback source policy is malformed"
    if WHISKY_POLICY_ANCHOR != "https://raw.githubusercontent.com/Homebrew/homebrew-cask/87180be1e381499a994990a044944580d180be44/Casks/w/whisky.rb":
        return "authorized Whisky policy anchor is malformed"
    if WHISKY_EXPECTED_SHA256 != "62fce6aa7034cc84e4809a35cb46af37e7932368102450dd2b3d4a18cbc7b94e":
        return "authorized Whisky digest policy is malformed"
    return None



def _source_kind(source: str) -> Optional[Dict[str, str]]:
    if source == WHISKY_OFFICIAL_SOURCE:
        return {
            "source_kind": "OFFICIAL_RELEASE",
            "provenance_status": "CONTENT_ANCHOR_FROM_OFFICIAL_HOMEBREW_CASK",
        }
    if source == WHISKY_PROJECT_FALLBACK_SOURCE:
        return {
            "source_kind": "PROJECT_FALLBACK",
            "provenance_status": "CONTENT_ANCHORED_SOURCE_PROVENANCE_UNCONFIRMED",
        }
    return None



def source_policy() -> Dict[str, Any]:
    """Describe the fixed source and content identity without mutation authority."""

    return {
        "schema_version": 1,
        "operation": "whisky-source-policy",
        "artifact": "Whisky.app",
        "version": WHISKY_VERSION,
        "repository": WHISKY_REPOSITORY,
        "release_tag": WHISKY_RELEASE_TAG,
        "official_source": WHISKY_OFFICIAL_SOURCE,
        "project_fallback_source": WHISKY_PROJECT_FALLBACK_SOURCE,
        "expected_sha256": WHISKY_EXPECTED_SHA256,
        "policy_anchor": WHISKY_POLICY_ANCHOR,
        "verification_method": "sha256 against fixed project policy",
        "signature_status": "not-verified",
        "signer_authorized": False,
        "execution_authority": False,
        "evidence_scope": "descriptive-only; never grants installation authority",
        "result": "success" if _policy_error() is None else "blocked",
        "reason": _policy_error() or "fixed Whisky release identity is well-formed",
    }



def verify_download(path: str | Path, source: str) -> Dict[str, Any]:
    """Verify one archive against the fixed digest and exact approved source URL."""

    result: Dict[str, Any] = {
        "schema_version": 1,
        "operation": "verify-whisky-download",
        "artifact": "Whisky.app",
        "requested_source": source,
        "resolved_source": source,
        "authorized_repository": WHISKY_REPOSITORY,
        "authorized_version": WHISKY_VERSION,
        "authorized_release_tag": WHISKY_RELEASE_TAG,
        "expected_sha256": WHISKY_EXPECTED_SHA256,
        "policy_anchor": WHISKY_POLICY_ANCHOR,
        "observed_sha256": None,
        "source_kind": None,
        "integrity_status": "not-verified",
        "provenance_status": "not-verified",
        "signature_status": "not-verified",
        "signer_authorized": False,
        "execution_authority": False,
        "result": "blocked",
        "reason": "not-run",
    }
    policy_error = _policy_error()
    if policy_error:
        result["reason"] = policy_error
        return result
    source_info = _source_kind(source)
    if source_info is None:
        result["reason"] = "source URL is not an exact authorized Whisky release or fallback"
        return result
    result.update(source_info)
    candidate = Path(path)
    if candidate.is_symlink():
        result["reason"] = "Whisky archive must be a regular file, not a symlink"
        return result
    if not candidate.exists() or not candidate.is_file():
        result["reason"] = "Whisky archive is missing or is not a regular file"
        return result
    digest = hashlib.sha256()
    try:
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        result["reason"] = f"cannot read Whisky archive: {exc}"
        return result
    observed = digest.hexdigest()
    result["observed_sha256"] = observed
    if observed != WHISKY_EXPECTED_SHA256:
        result["reason"] = "Whisky archive digest does not match the fixed release identity"
        return result
    result.update(
        {
            "integrity_status": "match",
            "result": "success",
            "reason": "Whisky archive matches the fixed release content identity",
        }
    )
    return result


def _read_verified_archive(path: str | Path, source: str) -> tuple[Dict[str, Any], Optional[Any]]:
    """Copy and verify one archive snapshot held by an anonymous open file."""

    candidate = Path(path)
    result: Dict[str, Any] = {
        "schema_version": 1,
        "operation": "verify-whisky-download",
        "artifact": "Whisky.app",
        "requested_source": source,
        "resolved_source": source,
        "authorized_repository": WHISKY_REPOSITORY,
        "authorized_version": WHISKY_VERSION,
        "authorized_release_tag": WHISKY_RELEASE_TAG,
        "expected_sha256": WHISKY_EXPECTED_SHA256,
        "policy_anchor": WHISKY_POLICY_ANCHOR,
        "observed_sha256": None,
        "source_kind": None,
        "integrity_status": "not-verified",
        "provenance_status": "not-verified",
        "signature_status": "not-verified",
        "signer_authorized": False,
        "execution_authority": False,
        "result": "blocked",
        "reason": "not-run",
    }
    policy_error = _policy_error()
    if policy_error:
        result["reason"] = policy_error
        return result, None
    source_info = _source_kind(source)
    if source_info is None:
        result["reason"] = "source URL is not an exact authorized Whisky release or fallback"
        return result, None
    result.update(source_info)
    if candidate.is_symlink():
        result["reason"] = "Whisky archive must be a regular file, not a symlink"
        return result, None
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(candidate, flags)
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                result.update({"result": "blocked", "integrity_status": "not-verified", "reason": "Whisky archive changed to a non-regular file"})
                return result, None
            snapshot = tempfile.TemporaryFile(mode="w+b")
            digest = hashlib.sha256()
            with os.fdopen(descriptor, "rb") as stream:
                descriptor = -1
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
                    snapshot.write(chunk)
        finally:
            if descriptor != -1:
                os.close(descriptor)
    except OSError as exc:
        result.update({"result": "blocked", "integrity_status": "not-verified", "reason": f"cannot snapshot Whisky archive: {exc}"})
        return result, None
    observed = digest.hexdigest()
    result["observed_sha256"] = observed
    if observed != WHISKY_EXPECTED_SHA256:
        snapshot.close()
        result.update({"result": "blocked", "integrity_status": "mismatch", "observed_sha256": observed, "reason": "Whisky archive changed while being snapshotted"})
        return result, None
    result.update({"result": "success", "integrity_status": "match", "reason": "Whisky archive matches the fixed release content identity", "verification_method": "sha256 against fixed project policy from one anonymous archive snapshot"})
    snapshot.flush()
    snapshot.seek(0)
    return result, snapshot


def _safe_zip_member(info: zipfile.ZipInfo) -> Optional[str]:
    name = info.filename
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or "\\" in name:
        return "archive contains an absolute path or path traversal"
    mode = (info.external_attr >> 16) & 0o170000
    if mode == stat.S_IFLNK:
        return "archive contains a symlink"
    if mode not in (0, stat.S_IFREG, stat.S_IFDIR):
        return "archive contains a special file"
    return None


def extract_verified(path: str | Path, source: str, destination: str | Path) -> Dict[str, Any]:
    """Verify and extract from the same immutable byte snapshot without mutation authority."""

    result, snapshot = _read_verified_archive(path, source)
    result.update({"operation": "verify-and-extract-whisky-download", "destination": str(destination)})
    if snapshot is None:
        return result
    target = Path(destination)
    if target.is_symlink() or not target.exists() or not target.is_dir():
        snapshot.close()
        result.update({"result": "blocked", "reason": "extraction destination must be an existing regular directory"})
        return result
    try:
        if any(target.iterdir()):
            snapshot.close()
            result.update({"result": "blocked", "reason": "extraction destination must be empty"})
            return result
        with snapshot, zipfile.ZipFile(snapshot) as archive:
            seen_paths: set[str] = set()
            for info in archive.infolist():
                member_error = _safe_zip_member(info)
                if member_error:
                    result.update({"result": "blocked", "reason": member_error})
                    return result
                posix_path = PurePosixPath(info.filename)
                normalized = "/".join(unicodedata.normalize("NFC", part).casefold() for part in posix_path.parts)
                if normalized in seen_paths:
                    result.update({"result": "blocked", "reason": "archive contains colliding member paths"})
                    return result
                seen_paths.add(normalized)
            snapshot.seek(0)
            process = subprocess.run(
                ["/usr/bin/ditto", "-xk", f"/dev/fd/{snapshot.fileno()}", str(target)],
                check=False,
                capture_output=True,
                text=True,
                pass_fds=(snapshot.fileno(),),
            )
            if process.returncode:
                detail = (process.stderr or process.stdout).strip()
                result.update({"result": "blocked", "reason": f"verified archive extraction failed ({process.returncode}): {detail[:500]}"})
                return result
    except (OSError, UnicodeDecodeError, zipfile.BadZipFile, RuntimeError) as exc:
        if not snapshot.closed:
            snapshot.close()
        result.update({"result": "blocked", "reason": f"cannot extract verified Whisky archive: {exc}"})
        return result
    app_bundle = target / "Whisky.app"
    if app_bundle.is_symlink() or not app_bundle.is_dir():
        result.update({"result": "blocked", "reason": "verified archive did not produce a regular Whisky.app directory"})
        return result
    result.update({"result": "success", "reason": "Whisky archive verified and extracted from one anonymous archive snapshot"})
    return result



def _print_result(value: Dict[str, Any]) -> int:
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0 if value.get("result") == "success" else 1



def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-only Whisky release verifier")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("source-policy", help="print the fixed Whisky source policy")
    verify = sub.add_parser("verify-download", help="verify a downloaded Whisky archive")
    verify.add_argument("--file", required=True)
    verify.add_argument("--source", required=True)
    extract = sub.add_parser("verify-and-extract", help="verify and extract one Whisky archive snapshot")
    extract.add_argument("--file", required=True)
    extract.add_argument("--source", required=True)
    extract.add_argument("--destination", required=True)
    return parser



def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "source-policy":
        return _print_result(source_policy())
    if args.command == "verify-download":
        return _print_result(verify_download(args.file, args.source))
    if args.command == "verify-and-extract":
        return _print_result(extract_verified(args.file, args.source, args.destination))
    raise WhiskyPolicyError("unsupported command")


if __name__ == "__main__":
    raise SystemExit(main())
