#!/usr/bin/env python3
"""Small deterministic uaRO execution primitives.

This spike contains only the Phase 2A FCOM classification and patch
transaction.  It intentionally does not discover uaRO paths or perform any
other installation, repair, backup, or uninstall work.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import stat
import sys
from typing import Dict, Optional, Tuple


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
    return {
        "operation": operation,
        "target": str(target),
        "backup": str(target.with_name(target.name + ".orig-backup")),
        "mutation": False,
        "backup_created": False,
        "verification": "not-run",
    }


def _read_and_classify(target: Path, operation: str) -> Tuple[Dict[str, object], Optional[bytes]]:
    result = _target_record(target, operation)
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
    result.update({"result": "blocked", "reason": reason, "verification": "not-run"})
    return result


def _validate_backup(backup_bytes: bytes, original: bytes) -> Optional[str]:
    if len(backup_bytes) != len(original):
        return "existing original backup has a different size"
    if _site_state(backup_bytes, SITE_A_OFFSET, A_UNPATCHED, A_PATCHED) != "unpatched":
        return "existing original backup does not contain unpatched Site A bytes"
    if _site_state(backup_bytes, SITE_B_OFFSET, B_UNPATCHED, B_PATCHED) != "unpatched":
        return "existing original backup does not contain unpatched Site B bytes"
    return None


def apply_fcom(target_path: str | Path) -> Dict[str, object]:
    """Apply the approved two-site transaction to an explicit target."""

    target = Path(target_path)
    result, original = _read_and_classify(target, "fcom-apply")
    if original is None:
        return result

    state = result["state"]
    if state != "UNPATCHED":
        if state == "PATCHED":
            result.update({"result": "success", "reason": "already patched; no-op"})
            return result
        return _blocked(result, f"FCOM state {state} is not patchable")

    backup = target.with_name(target.name + ".orig-backup")
    try:
        if backup.exists():
            backup_bytes = backup.read_bytes()
            backup_error = _validate_backup(backup_bytes, original)
            if backup_error:
                return _blocked(result, backup_error)
        else:
            shutil.copy2(target, backup)
            result["backup_created"] = True
            backup_bytes = backup.read_bytes()
            if backup_bytes != original:
                return _blocked(result, "new original backup does not exactly match target")
    except OSError as exc:
        return _blocked(result, f"cannot validate/create original backup: {exc}")

    try:
        target.chmod(target.stat().st_mode | stat.S_IWUSR)
        result["mutation"] = True
        patched = bytearray(original)
        patched[SITE_A_OFFSET : SITE_A_OFFSET + 1] = A_PATCHED
        patched[SITE_B_OFFSET : SITE_B_OFFSET + 4] = B_PATCHED
        target.write_bytes(patched)
        final = target.read_bytes()
    except OSError as exc:
        return _blocked(result, f"FCOM patch write/read-back failed: {exc}")

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

    result.update(
        {
            "post_state": "PATCHED",
            "result": "success",
            "reason": "patched and verified",
            "verification": "passed",
        }
    )
    return result


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
    args = parser.parse_args(argv)

    if args.area == "fcom" and args.operation == "check":
        return _emit(check_fcom(args.target))
    if args.area == "fcom" and args.operation == "apply":
        return _emit(apply_fcom(args.target))
    parser.error("unsupported operation")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
