#!/usr/bin/env python3
"""Direct tests for the deterministic FCOM spike implementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import uaro  # noqa: E402


def fixture_binary(site_a: bytes, site_b: bytes, size: int | None = None) -> bytes:
    required = max(
        uaro.SITE_A_OFFSET + len(uaro.A_UNPATCHED),
        uaro.SITE_B_OFFSET + len(uaro.B_UNPATCHED),
    )
    total = max(size or required + 32, required)
    data = bytearray((index * 17) % 251 for index in range(total))
    data[uaro.SITE_A_OFFSET : uaro.SITE_A_OFFSET + 1] = site_a
    data[uaro.SITE_B_OFFSET : uaro.SITE_B_OFFSET + 4] = site_b
    return bytes(data)


class FcomSpikeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="uaro-fcom-spike-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def target(self, data: bytes) -> Path:
        path = self.root / "setup.exe"
        path.write_bytes(data)
        return path

    @staticmethod
    def backup_for(target: Path) -> Path:
        return target.with_name(target.name + ".orig-backup")

    def test_check_unpatched_is_structured_and_read_only(self) -> None:
        target = self.target(fixture_binary(uaro.A_UNPATCHED, uaro.B_UNPATCHED))
        before = hashlib.sha256(target.read_bytes()).digest()
        result = uaro.check_fcom(target)
        self.assertEqual(result["state"], "UNPATCHED")
        self.assertEqual(result["site_a"], "unpatched")
        self.assertEqual(result["site_b"], "unpatched")
        self.assertFalse(result["mutation"])
        self.assertFalse(self.backup_for(target).exists())
        self.assertEqual(hashlib.sha256(target.read_bytes()).digest(), before)

    def test_check_patched(self) -> None:
        target = self.target(fixture_binary(uaro.A_PATCHED, uaro.B_PATCHED))
        result = uaro.check_fcom(target)
        self.assertEqual(result["state"], "PATCHED")
        self.assertEqual(result["result"], "success")
        self.assertFalse(result["mutation"])

    def assert_blocked_without_mutation(self, data: bytes, expected_state: str) -> None:
        target = self.target(data)
        before = target.read_bytes()
        result = uaro.apply_fcom(target)
        self.assertEqual(result["result"], "blocked")
        self.assertEqual(result["state"], expected_state)
        self.assertFalse(result["mutation"])
        self.assertEqual(target.read_bytes(), before)
        self.assertFalse(self.backup_for(target).exists())

    def test_site_a_unknown_is_fail_closed(self) -> None:
        self.assert_blocked_without_mutation(
            fixture_binary(b"\x00", uaro.B_UNPATCHED), "UNKNOWN"
        )

    def test_site_b_unknown_is_fail_closed(self) -> None:
        self.assert_blocked_without_mutation(
            fixture_binary(uaro.A_UNPATCHED, b"\x00\x00\x00\x00"), "UNKNOWN"
        )

    def test_a_patched_b_unpatched_is_mixed_and_fail_closed(self) -> None:
        self.assert_blocked_without_mutation(
            fixture_binary(uaro.A_PATCHED, uaro.B_UNPATCHED), "MIXED"
        )

    def test_a_unpatched_b_patched_is_mixed_and_fail_closed(self) -> None:
        self.assert_blocked_without_mutation(
            fixture_binary(uaro.A_UNPATCHED, uaro.B_PATCHED), "MIXED"
        )

    def test_truncated_target_is_fail_closed(self) -> None:
        self.assert_blocked_without_mutation(
            b"\x00" * (uaro.SITE_B_OFFSET + 2), "TRUNCATED"
        )

    def test_valid_unpatched_apply_creates_exact_backup_and_exact_diff(self) -> None:
        original = fixture_binary(uaro.A_UNPATCHED, uaro.B_UNPATCHED)
        target = self.target(original)
        result = uaro.apply_fcom(target)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["pre_state"], "UNPATCHED")
        self.assertEqual(result["post_state"], "PATCHED")
        self.assertTrue(result["mutation"])
        self.assertTrue(result["backup_created"])
        self.assertEqual(self.backup_for(target).read_bytes(), original)

        final = target.read_bytes()
        expected = bytearray(original)
        expected[uaro.SITE_A_OFFSET : uaro.SITE_A_OFFSET + 1] = uaro.A_PATCHED
        expected[uaro.SITE_B_OFFSET : uaro.SITE_B_OFFSET + 4] = uaro.B_PATCHED
        self.assertEqual(final, bytes(expected))
        changed = {i for i, (before, after) in enumerate(zip(original, final)) if before != after}
        self.assertEqual(changed, uaro.EXPECTED_CHANGED_OFFSETS)

    def test_already_patched_is_true_noop(self) -> None:
        original = fixture_binary(uaro.A_PATCHED, uaro.B_PATCHED)
        target = self.target(original)
        result = uaro.apply_fcom(target)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["reason"], "already patched; no-op")
        self.assertFalse(result["mutation"])
        self.assertFalse(result["backup_created"])
        self.assertEqual(target.read_bytes(), original)
        self.assertFalse(self.backup_for(target).exists())

    def test_existing_valid_backup_is_preserved(self) -> None:
        original = fixture_binary(uaro.A_UNPATCHED, uaro.B_UNPATCHED)
        target = self.target(original)
        backup = self.backup_for(target)
        backup.write_bytes(original)
        result = uaro.apply_fcom(target)
        self.assertEqual(result["result"], "success")
        self.assertFalse(result["backup_created"])
        self.assertEqual(backup.read_bytes(), original)

    def test_cli_check_emits_json_and_apply_has_stable_exit(self) -> None:
        target = self.target(fixture_binary(uaro.A_UNPATCHED, uaro.B_UNPATCHED))
        check = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "uaro.py"), "fcom", "check", str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(check.returncode, 0)
        self.assertEqual(json.loads(check.stdout)["state"], "UNPATCHED")

        apply = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "uaro.py"), "fcom", "apply", str(target)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(apply.returncode, 0)
        self.assertEqual(json.loads(apply.stdout)["post_state"], "PATCHED")


if __name__ == "__main__":
    unittest.main()
