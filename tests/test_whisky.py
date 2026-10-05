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
import tarfile
import unittest
from unittest import mock
import zipfile
import shutil

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import whisky  # noqa: E402
import whiskywine  # noqa: E402


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

    def test_troubleshooting_cask_row_matches_current_whisky_route(self) -> None:
        troubleshooting = (Path(__file__).resolve().parents[1] / "TROUBLESHOOTING.md").read_text()
        row = next(line for line in troubleshooting.splitlines() if "`brew install --cask whisky` exits 0" in line)
        self.assertIn("diagnostic probe only", row)
        self.assertIn("exact v2.3.5 release verifier", row)
        self.assertNotIn("fall back to GitHub release zip only if truly absent", row)

    def test_troubleshooting_whiskywine_fallback_order_matches_current_route(self) -> None:
        troubleshooting = (Path(__file__).resolve().parents[1] / "TROUBLESHOOTING.md").read_text()
        row = next(line for line in troubleshooting.splitlines() if "`command not found: wine64`" in line)
        self.assertIn("repo's archived runtime first", row)
        self.assertIn("Internet Archive only as the last-resort fallback", row)
        self.assertIn("provenance in v1", row)

    def test_troubleshooting_installer_row_distinguishes_setup_tools(self) -> None:
        troubleshooting = (Path(__file__).resolve().parents[1] / "TROUBLESHOOTING.md").read_text()
        row = next(line for line in troubleshooting.splitlines() if "Inno Setup installs into the bottle" in line)
        self.assertIn("UaRO_Setup.exe", row)
        self.assertIn("Step 7", row)
        self.assertIn("RO OpenSetup tool", row)
        self.assertNotIn("wine64 setup.exe /DIR", row)

    def test_launcher_process_cleanup_stays_bottle_scoped(self) -> None:
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
        step11 = skill[skill.index("## Step 11 — Build the three launcher .app bundles") :]
        self.assertNotIn("pkill -f", step11)
        self.assertIn("wineserver -k", step11)

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

    def test_whiskywine_route_uses_safe_runtime_extractor(self) -> None:
        skill = (Path(__file__).resolve().parents[1] / "SKILL.md").read_text()
        start = skill.index("## Step 4 — WhiskyWine runtime")
        end = skill.index("## Step 5 —", start)
        section = skill[start:end]
        self.assertIn('scripts/whiskywine.py" extract-runtime', section)
        self.assertNotIn("tar -xzf Libraries.tar.gz -C", section)

    def test_whiskywine_extractor_blocks_traversal_and_links(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-extract-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                info.mode = 0o755
                bundle.addfile(info, io.BytesIO(body))
            result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "success")
            self.assertEqual(result["lifecycle_state"], "PUBLISHED_VERIFIED")
            self.assertEqual(result["post_state"], "PUBLISHED")
            self.assertFalse(result["execution_authority"])
            self.assertEqual(result["provenance"], "unconfirmed")
            self.assertEqual((destination / "Libraries/Wine/bin/wine64").read_bytes(), b"runtime")

            traversal = root / "traversal.tar.gz"
            with tarfile.open(traversal, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                bundle.addfile(info, io.BytesIO(b"x"))
            blocked = whiskywine.extract_runtime(traversal, root / "blocked")
            self.assertEqual(blocked["result"], "blocked")
            self.assertFalse((root / "escape").exists())

            link_archive = root / "link.tar.gz"
            with tarfile.open(link_archive, "w:gz") as bundle:
                info = tarfile.TarInfo("Libraries/link")
                info.type = tarfile.SYMTYPE
                info.linkname = "/tmp/outside"
                bundle.addfile(info)
            link_blocked = whiskywine.extract_runtime(link_archive, root / "link-blocked")
            self.assertEqual(link_blocked["result"], "blocked")

    def test_whiskywine_rejects_multiple_top_level_roots_before_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-multi-root-") as temp:
            root = Path(temp)
            archive = root / "multi.tar.gz"
            destination = root / "support"
            with tarfile.open(archive, "w:gz") as bundle:
                for name, body in (("Libraries/Wine/bin/wine64", b"wine"), ("Other/extra", b"extra")):
                    info = tarfile.TarInfo(name)
                    info.size = len(body)
                    bundle.addfile(info, io.BytesIO(body))
            result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertEqual(result["lifecycle_state"], "BLOCKED_NO_MUTATION")
            self.assertFalse(destination.exists())

    def test_whiskywine_rejects_empty_runtime_before_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-empty-runtime-") as temp:
            root = Path(temp)
            archive = root / "empty.tar.gz"
            destination = root / "support"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("Libraries")
                info.type = tarfile.DIRTYPE
                bundle.addfile(info)
            result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertIn("Wine/bin/wine64", result["reason"])
            self.assertFalse(destination.exists())

    def test_whiskywine_staging_failure_does_not_create_destination(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-stage-failure-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            def fail_copy(_source: object, output: object) -> None:
                output.write(b"partial")
                raise OSError("injected extraction failure")

            with mock.patch.object(whiskywine.shutil, "copyfileobj", side_effect=fail_copy):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertEqual(result["lifecycle_state"], "BLOCKED_NO_MUTATION")
            self.assertFalse(destination.exists())

    def test_whiskywine_rejects_ancestor_symlink_before_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-ancestor-") as temp:
            root = Path(temp)
            outside = root / "outside"
            outside.mkdir()
            alias = root / "alias"
            alias.symlink_to(outside, target_is_directory=True)
            archive = root / "Libraries.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))
            result = whiskywine.extract_runtime(archive, alias / "support")
            self.assertEqual(result["result"], "blocked")
            self.assertIn("symlink path component", result["reason"])
            self.assertFalse((outside / "support").exists())

    def test_whiskywine_rejects_traversal_before_symlink_resolution(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-traversal-alias-") as temp:
            root = Path(temp)
            outside = root / "outside" / "inner"
            outside.mkdir(parents=True)
            alias = root / "alias"
            alias.symlink_to(outside, target_is_directory=True)
            archive = root / "Libraries.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))
            result = whiskywine.extract_runtime(archive, alias / ".." / "support")
            self.assertEqual(result["result"], "blocked")
            self.assertIn("symlink path component", result["reason"])
            self.assertFalse((outside / "support").exists())

    def test_whiskywine_destination_swap_is_ambiguous_without_outside_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-destination-race-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            destination.mkdir()
            outside = root / "outside"
            outside.mkdir()
            original_destination = root / "support-original"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            real_replace = whiskywine.os.replace
            swapped = False

            def swap_destination_then_replace(
                source: str | os.PathLike[str],
                target: str | os.PathLike[str],
                **kwargs: object,
            ) -> None:
                nonlocal swapped
                self.assertIsNotNone(kwargs.get("src_dir_fd"))
                self.assertIsNotNone(kwargs.get("dst_dir_fd"))
                if not swapped:
                    destination.rename(original_destination)
                    destination.symlink_to(outside, target_is_directory=True)
                    swapped = True
                real_replace(source, target, **kwargs)

            with mock.patch.object(whiskywine.os, "replace", side_effect=swap_destination_then_replace):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertEqual(result["lifecycle_state"], "AMBIGUOUS_NEEDS_INSPECTION")
            self.assertEqual(result["post_state"], "UNKNOWN")
            self.assertTrue((destination / "Libraries").exists() is False)
            self.assertTrue((original_destination / "Libraries/Wine/bin/wine64").is_file())
            self.assertFalse((outside / "Libraries").exists())

    def test_whiskywine_parent_swap_reports_created_destination_mutation(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-parent-race-") as temp:
            root = Path(temp)
            parent = root / "parent"
            parent.mkdir()
            outside = root / "outside"
            outside.mkdir()
            archive = root / "Libraries.tar.gz"
            destination = parent / "support"
            moved_parent = root / "parent-original"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            real_mkdir = whiskywine.os.mkdir
            swapped = False

            def mkdir_then_swap(path: str | os.PathLike[str], mode: int = 0o777, *, dir_fd: int | None = None) -> None:
                nonlocal swapped
                real_mkdir(path, mode, dir_fd=dir_fd)
                if dir_fd is not None and path == "support" and not swapped:
                    destination.parent.rename(moved_parent)
                    destination.parent.symlink_to(outside, target_is_directory=True)
                    (moved_parent / "support" / "concurrent").write_bytes(b"race")
                    swapped = True

            with mock.patch.object(whiskywine.os, "mkdir", side_effect=mkdir_then_swap):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertTrue(result["mutation"])
            self.assertEqual(result["lifecycle_state"], "AMBIGUOUS_NEEDS_INSPECTION")
            self.assertFalse((outside / "support").exists())
            self.assertTrue((moved_parent / "support/concurrent").is_file())

    def test_whiskywine_pre_publish_failure_with_residue_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-prepublish-residue-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            def leave_residue_then_fail(
                source: str | os.PathLike[str],
                target: str | os.PathLike[str],
                **kwargs: object,
            ) -> None:
                destination.joinpath("concurrent").write_bytes(b"race")
                raise OSError("injected pre-publish failure")

            with mock.patch.object(whiskywine.os, "replace", side_effect=leave_residue_then_fail):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertTrue(result["mutation"])
            self.assertEqual(result["lifecycle_state"], "AMBIGUOUS_NEEDS_INSPECTION")
            self.assertTrue((destination / "concurrent").is_file())

    def test_whiskywine_post_manifest_swap_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-post-manifest-race-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            destination.mkdir()
            outside = root / "outside"
            outside.mkdir()
            original_destination = root / "support-original"
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            real_manifest = whiskywine._tree_manifest_at_fd
            swapped = False

            def manifest_then_swap(descriptor: int) -> dict[str, tuple[str, int, str]]:
                nonlocal swapped
                if not swapped:
                    destination.rename(original_destination)
                    shutil.copytree(original_destination / "Libraries", outside / "Libraries")
                    destination.symlink_to(outside, target_is_directory=True)
                    swapped = True
                return real_manifest(descriptor)

            with mock.patch.object(whiskywine, "_tree_manifest_at_fd", side_effect=manifest_then_swap):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertTrue(result["mutation"])
            self.assertEqual(result["lifecycle_state"], "AMBIGUOUS_NEEDS_INSPECTION")
            self.assertTrue((original_destination / "Libraries/Wine/bin/wine64").is_file())

    def test_whiskywine_published_child_swap_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-child-race-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            destination.mkdir()
            outside = root / "outside"
            outside.mkdir()
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            real_manifest = whiskywine._tree_manifest_at_fd
            swapped = False

            def manifest_then_swap_child(descriptor: int) -> dict[str, tuple[str, int, str]]:
                nonlocal swapped
                if not swapped:
                    published = destination / "Libraries"
                    moved = destination / "Libraries-original"
                    published.rename(moved)
                    shutil.copytree(moved, outside / "Libraries")
                    published.symlink_to(outside / "Libraries", target_is_directory=True)
                    swapped = True
                return real_manifest(descriptor)

            with mock.patch.object(whiskywine, "_tree_manifest_at_fd", side_effect=manifest_then_swap_child):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "blocked")
            self.assertTrue(result["mutation"])
            self.assertEqual(result["lifecycle_state"], "AMBIGUOUS_NEEDS_INSPECTION")
            self.assertTrue((destination / "Libraries-original/Wine/bin/wine64").is_file())

    def test_whiskywine_post_rename_error_reports_verified_publish(self) -> None:
        with tempfile.TemporaryDirectory(prefix="whiskywine-post-rename-") as temp:
            root = Path(temp)
            archive = root / "Libraries.tar.gz"
            destination = root / "support"
            destination.mkdir()
            with tarfile.open(archive, "w:gz") as bundle:
                body = b"runtime"
                info = tarfile.TarInfo("Libraries/Wine/bin/wine64")
                info.size = len(body)
                bundle.addfile(info, io.BytesIO(body))

            real_replace = whiskywine.os.replace

            def move_then_raise(
                source: str | os.PathLike[str],
                target: str | os.PathLike[str],
                **kwargs: object,
            ) -> None:
                real_replace(source, target, **kwargs)
                raise OSError("injected post-rename failure")

            with mock.patch.object(whiskywine.os, "replace", side_effect=move_then_raise):
                result = whiskywine.extract_runtime(archive, destination)
            self.assertEqual(result["result"], "success")
            self.assertEqual(result["lifecycle_state"], "PUBLISHED_VERIFIED")
            self.assertTrue((destination / "Libraries/Wine/bin/wine64").is_file())

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
