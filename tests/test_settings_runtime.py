#!/usr/bin/env python3
"""Direct tests for the Stage 2.2A bundled Settings runtime artifact."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_settings_runtime as runtime  # noqa: E402


class SettingsRuntimeTests(unittest.TestCase):
    def make_repo_fixture(self, parent: Path, *, origin: str = next(iter(runtime.EXPECTED_ORIGINS))) -> Path:
        repo = parent / "canonical-repo"
        (repo / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts" / "uaro.py", repo / "scripts" / "uaro.py")
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        subprocess.run(["git", "-C", str(repo), "add", "scripts/uaro.py"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "fixture"], check=True)
        return repo

    def build(self, repo: Path, destination: Path) -> dict:
        return runtime.build_settings_runtime(repo, destination)

    def test_valid_artifact_and_byte_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "uaro-runtime"
            built = self.build(ROOT, destination)
            verified = runtime.verify_settings_runtime(destination)
            self.assertEqual(built["result"], "success")
            self.assertEqual(verified["result"], "success")
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest), runtime.REQUIRED_MANIFEST_KEYS)
            self.assertEqual(manifest["canonical_source"], "scripts/uaro.py")
            self.assertEqual(manifest["executor_relpath"], "uaro.py")
            self.assertEqual(manifest["interface_version"], 1)
            self.assertEqual(manifest["schema_version"], 1)
            self.assertEqual((destination / "uaro.py").read_bytes(), (ROOT / "scripts/uaro.py").read_bytes())
            self.assertEqual(
                built["executor_sha256"], hashlib.sha256((destination / "uaro.py").read_bytes()).hexdigest()
            )

    def test_repository_independence_after_source_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            destination = root / "runtime"
            self.build(repo, destination)
            shutil.rmtree(repo)
            self.assertEqual(runtime.verify_settings_runtime(destination)["result"], "success")

    def test_tamper_and_missing_artifacts_fail_closed(self) -> None:
        cases = ("tamper", "missing-executor", "missing-manifest", "malformed-manifest", "digest")
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                destination = root / "runtime"
                self.build(ROOT, destination)
                if case == "tamper":
                    path = destination / "uaro.py"
                    data = bytearray(path.read_bytes())
                    data[0] ^= 1
                    path.write_bytes(data)
                elif case == "missing-executor":
                    (destination / "uaro.py").unlink()
                elif case == "missing-manifest":
                    (destination / "MANIFEST.json").unlink()
                elif case == "malformed-manifest":
                    (destination / "MANIFEST.json").write_text("{", encoding="utf-8")
                else:
                    manifest_path = destination / "MANIFEST.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["executor_sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(runtime.SettingsRuntimeVerificationError):
                    runtime.verify_settings_runtime(destination)

    def test_manifest_schema_path_and_identity_validation(self) -> None:
        mutations = {
            "schema_version": 2,
            "interface_version": 2,
            "executor_relpath": "elsewhere/uaro.py",
            "canonical_source": "other.py",
            "source_commit": "not-a-commit",
            "executor_sha256": "not-a-digest",
        }
        for key, value in mutations.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                destination = Path(temp) / "runtime"
                self.build(ROOT, destination)
                manifest_path = destination / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(runtime.SettingsRuntimeVerificationError):
                    runtime.verify_settings_runtime(destination)

    def test_dirty_canonical_source_blocks_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            source = repo / "scripts/uaro.py"
            source.write_bytes(source.read_bytes() + b"\n# dirty\n")
            with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "dirty"):
                self.build(repo, root / "runtime")

    def test_wrong_repository_blocks_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root, origin="https://example.invalid/unrelated.git")
            with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "origin"):
                self.build(repo, root / "runtime")

    def test_repeated_generation_is_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "first"
            second = root / "second"
            self.build(ROOT, first)
            self.build(ROOT, second)
            self.assertEqual((first / "uaro.py").read_bytes(), (second / "uaro.py").read_bytes())
            self.assertEqual((first / "MANIFEST.json").read_bytes(), (second / "MANIFEST.json").read_bytes())

    def test_builder_contains_no_second_executor(self) -> None:
        source = (ROOT / "scripts/build_settings_runtime.py").read_text(encoding="utf-8")
        for forbidden in ("0x2C0CD", "SITE_A_OFFSET", "dcd8dfe0", "savedata", "_site_state"):
            self.assertNotIn(forbidden, source)
        self.assertIn("source.read_bytes()", source)
        self.assertIn("executor_sha256", source)

    def test_codesign_ordering_contract_is_documented(self) -> None:
        source = (ROOT / "scripts/build_settings_runtime.py").read_text(encoding="utf-8")
        expected = (
            "    generate runtime resources",
            "    -> verify runtime resources",
            "    -> codesign app bundle",
            "    -> verify app signature",
            "    -> deploy",
        )
        positions = [source.index(item) for item in expected]
        self.assertEqual(positions, sorted(positions))


if __name__ == "__main__":
    unittest.main()
