#!/usr/bin/env python3
"""Direct adversarial tests for the fixed Whisky release identity."""

from __future__ import annotations

import hashlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import whisky  # noqa: E402


class WhiskyPolicyTests(unittest.TestCase):
    def test_uaro_installer_route_stops_before_stale_archive_extraction(self) -> None:
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
        start = skill.index("## Step 6 — Download & extract the uaRO installer")
        end = skill.index("## Step 7 — Run the installer", start)
        section = skill[start:end]
        block_start = section.index("```bash")
        block_end = section.index("```", block_start + len("```bash"))
        block = section[block_start:block_end]
        self.assertIn("set -e", block)
        self.assertIn('INSTALLER_SOURCE="${INSTALLER_SOURCE:?', block)
        self.assertIn('PARTIAL_INSTALLER="$(mktemp', block)
        self.assertIn('mkdir -p "$(dirname "$INSTALLER_ZIP")"', block)
        self.assertIn('test -s "$PARTIAL_INSTALLER"', block)
        self.assertIn('mv -f "$PARTIAL_INSTALLER" "$INSTALLER_ZIP"', block)
        self.assertNotIn('curl -fL --progress-bar -o "$INSTALLER_ZIP"', block)
        self.assertNotIn('cp "$INSTALLER_SOURCE" "$INSTALLER_ZIP"', block)

    def test_skill_download_routes_fail_closed_and_extract_verified_snapshot(self) -> None:
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
        start = skill.index("## Step 3 — Whisky.app")
        end = skill.index("## Step 4 — WhiskyWine runtime", start)
        section = skill[start:end]
        self.assertIn("an existing Whisky installation is UNCONFIRMED", section)
        self.assertEqual(section.count("verify-and-extract"), 2)
        for source in ("IsaacMarovitz/Whisky/releases/download/v2.3.5/Whisky.zip", "auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/Whisky-app-2.3.5.zip"):
            block_start = section.index(source)
            block_start = section.rfind("```bash", 0, block_start)
            block_end = section.index("```", block_start + len("```bash"))
            block = section[block_start:block_end]
            self.assertIn("set -e", block)
            self.assertEqual(block.count("verify-and-extract"), 1)
            self.assertNotIn("ditto -xk", block)
            self.assertIn("mktemp -d /tmp/Whisky-extract.", block)

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

    def test_policy_rejects_mutated_source_and_anchor_constants(self) -> None:
        mutations = (
            ("WHISKY_OFFICIAL_SOURCE", "https://example.invalid/current.zip", "official source"),
            ("WHISKY_PROJECT_FALLBACK_SOURCE", "https://example.invalid/fallback.zip", "fallback source"),
            ("WHISKY_POLICY_ANCHOR", "https://example.invalid/policy.rb", "policy anchor"),
        )
        for name, value, label in mutations:
            with self.subTest(label=label), mock.patch.object(whisky, name, value):
                result = whisky.source_policy()
            self.assertEqual(result["result"], "blocked")
            self.assertIn("malformed", result["reason"])

    def test_policy_anchor_is_immutable_reviewed_cask_revision(self) -> None:
        self.assertIn("/87180be1e381499a994990a044944580d180be44/", whisky.WHISKY_POLICY_ANCHOR)

    def test_matching_official_bytes_pass(self) -> None:
        payload = b"official fixture bytes"
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="whisky-policy-") as temp:
            path = Path(temp) / "Whisky.zip"
            path.write_bytes(payload)
            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest), mock.patch.object(whisky, "_policy_error", return_value=None):
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
            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest), mock.patch.object(whisky, "_policy_error", return_value=None):
                result = whisky.verify_download(path, whisky.WHISKY_PROJECT_FALLBACK_SOURCE)
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["source_kind"], "PROJECT_FALLBACK")
        self.assertEqual(result["provenance_status"], "CONTENT_ANCHORED_SOURCE_PROVENANCE_UNCONFIRMED")

    def test_verify_and_extract_uses_verified_snapshot(self) -> None:
        payload_buffer = io.BytesIO()
        with zipfile.ZipFile(payload_buffer, "w") as archive:
            archive.writestr("Whisky.app/Contents/Info.plist", "fixture")
        payload = payload_buffer.getvalue()
        digest = hashlib.sha256(payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="whisky-extract-") as temp:
            root = Path(temp)
            archive_path = root / "Whisky.zip"
            destination = root / "extract"
            archive_path.write_bytes(payload)
            destination.mkdir()
            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest), mock.patch.object(whisky, "_policy_error", return_value=None):
                result = whisky.extract_verified(archive_path, whisky.WHISKY_OFFICIAL_SOURCE, destination)
            extracted = (destination / "Whisky.app/Contents/Info.plist").read_text()
        self.assertEqual(result["result"], "success")
        self.assertEqual(extracted, "fixture")
        self.assertIn("one anonymous archive snapshot", result["verification_method"])

    def test_verify_and_extract_resists_path_replacement_after_open(self) -> None:
        good_buffer = io.BytesIO()
        with zipfile.ZipFile(good_buffer, "w") as archive:
            archive.writestr("Whisky.app/good", "GOOD")
        evil_buffer = io.BytesIO()
        with zipfile.ZipFile(evil_buffer, "w") as archive:
            archive.writestr("Whisky.app/evil", "EVIL")
        good_payload = good_buffer.getvalue()
        digest = hashlib.sha256(good_payload).hexdigest()
        with tempfile.TemporaryDirectory(prefix="whisky-race-") as temp:
            root = Path(temp)
            archive_path = root / "Whisky.zip"
            destination = root / "extract"
            archive_path.write_bytes(good_payload)
            destination.mkdir()
            real_open = whisky.os.open

            def replace_after_open(path: str | bytes | os.PathLike[str], flags: int, *args: int) -> int:
                descriptor = real_open(path, flags, *args)
                if Path(path) == archive_path:
                    replacement = root / "replacement.zip"
                    replacement.write_bytes(evil_buffer.getvalue())
                    os.replace(replacement, archive_path)
                return descriptor

            with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest), mock.patch.object(whisky, "_policy_error", return_value=None), mock.patch.object(whisky.os, "open", replace_after_open):
                result = whisky.extract_verified(archive_path, whisky.WHISKY_OFFICIAL_SOURCE, destination)
            self.assertEqual(result["result"], "success")
            self.assertEqual((destination / "Whisky.app/good").read_text(), "GOOD")
            self.assertFalse((destination / "Whisky.app/evil").exists())

    def test_verify_and_extract_blocks_zip_traversal_and_symlink_members(self) -> None:
        for name in ("../escape", "Whisky.app/link"):
            payload_buffer = io.BytesIO()
            with zipfile.ZipFile(payload_buffer, "w") as archive:
                info = zipfile.ZipInfo(name)
                if name.endswith("link"):
                    info.create_system = 3
                    info.external_attr = (0o120777 << 16) | 0xA0000000
                archive.writestr(info, "target")
            payload = payload_buffer.getvalue()
            digest = hashlib.sha256(payload).hexdigest()
            with tempfile.TemporaryDirectory(prefix="whisky-extract-") as temp:
                root = Path(temp)
                archive_path = root / "Whisky.zip"
                destination = root / "extract"
                archive_path.write_bytes(payload)
                destination.mkdir()
                with mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", digest), mock.patch.object(whisky, "_policy_error", return_value=None):
                    result = whisky.extract_verified(archive_path, whisky.WHISKY_OFFICIAL_SOURCE, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertIn("archive contains", result["reason"])

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
        for value in ("candidate-controlled", "0" * 64, "a" * 64):
            with self.subTest(value=value), mock.patch.object(whisky, "WHISKY_EXPECTED_SHA256", value):
                result = whisky.source_policy()
            self.assertEqual(result["result"], "blocked")
            self.assertIn("digest policy", result["reason"])

    def test_result_is_json_serializable(self) -> None:
        payload = whisky.source_policy()
        json.dumps(payload)


if __name__ == "__main__":
    unittest.main()
