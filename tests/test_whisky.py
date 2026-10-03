#!/usr/bin/env python3
"""Direct adversarial tests for the fixed Whisky release identity."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import whisky  # noqa: E402


class WhiskyPolicyTests(unittest.TestCase):
    def test_source_policy_is_fixed_and_descriptive(self) -> None:
        policy = whisky.source_policy()
        self.assertEqual(policy["result"], "success")
        self.assertEqual(policy["version"], "2.3.5")
        self.assertEqual(policy["release_tag"], "v2.3.5")
        self.assertEqual(policy["official_source"], whisky.WHISKY_OFFICIAL_SOURCE)
        self.assertEqual(len(policy["expected_sha256"]), 64)
        self.assertIn("Homebrew/homebrew-cask", policy["policy_anchor"])
        self.assertFalse(policy["execution_authority"])
        self.assertEqual(policy["signature_status"], "not-verified")

    def test_policy_rejects_mutable_or_wrong_sources(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            path = Path(temp) / "Whisky.zip"
            path.write_bytes(b"candidate")
            for source in (
                "https://github.com/IsaacMarovitz/Whisky/archive/main.zip",
                "https://github.com/IsaacMarovitz/Whisky/releases/latest/download/Whisky.zip",
                "https://github.com/other/Whisky/releases/download/v2.3.5/Whisky.zip",
            ):
                result = whisky.verify_download(path, source)
                self.assertEqual(result["result"], "blocked")
                self.assertIn("exact authorized", result["reason"])

    def test_matching_official_bytes_pass(self) -> None:
        payload = b"official fixture bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            path = Path(temp) / "Whisky.zip"
            path.write_bytes(payload)
            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest):
                result = whisky.verify_download(path, whisky.WHISKY_OFFICIAL_SOURCE)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["integrity_status"], "match")
        self.assertEqual(result["source_kind"], "OFFICIAL_RELEASE")
        self.assertEqual(result["provenance_status"], "CONTENT_ANCHOR_FROM_OFFICIAL_HOMEBREW_CASK")
        self.assertFalse(result["execution_authority"])

    def test_matching_fallback_bytes_pass_with_provenance_disclosed(self) -> None:
        payload = b"archived project fixture bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            path = Path(temp) / "Whisky.zip"
            path.write_bytes(payload)
            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest):
                result = whisky.verify_download(path, whisky.WHISKY_PROJECT_FALLBACK_SOURCE)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["source_kind"], "PROJECT_FALLBACK")
        self.assertEqual(result["provenance_status"], "CONTENT_ANCHORED_SOURCE_PROVENANCE_UNCONFIRMED")

    def test_wrong_bytes_block_even_when_source_is_approved(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            path = Path(temp) / "Whisky.zip"
            path.write_bytes(b"tampered bytes")
            result = whisky.verify_download(path, whisky.WHISKY_OFFICIAL_SOURCE)
        self.assertEqual(result["result"], "blocked")
        self.assertEqual(result["integrity_status"], "not-verified")
        self.assertIn("digest", result["reason"])
        self.assertNotEqual(result["observed_sha256"], result["expected_sha256"])

    def test_missing_directory_and_symlink_block(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            root = Path(temp)
            missing = whisky.verify_download(root / "missing.zip", whisky.WHISKY_OFFICIAL_SOURCE)
            self.assertEqual(missing["result"], "blocked")
            target = root / "real.zip"
            target.write_bytes(b"bytes")
            link = root / "link.zip"
            link.symlink_to(target)
            linked = whisky.verify_download(link, whisky.WHISKY_OFFICIAL_SOURCE)
        self.assertEqual(linked["result"], "blocked")
        self.assertIn("symlink", linked["reason"])

    def test_malformed_fixed_policy_blocks(self) -> None:
        with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", "candidate-controlled"):
            result = whisky.source_policy()
        self.assertEqual(result["result"], "blocked")
        self.assertIn("digest policy", result["reason"])

    def test_result_is_json_serializable(self) -> None:
        payload = whisky.source_policy()
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
