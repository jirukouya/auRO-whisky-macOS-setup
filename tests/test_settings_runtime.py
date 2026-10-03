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
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_settings_runtime as runtime  # noqa: E402


class SettingsRuntimeTests(unittest.TestCase):
    def make_repo_fixture(self, parent: Path, *, origin: str = next(iter(runtime.EXPECTED_ORIGINS))) -> Path:
        repo = parent / "canonical-repo"
        (repo / "scripts").mkdir(parents=True)
        shutil.copy2(ROOT / "scripts" / "uaro.py", repo / "scripts" / "uaro.py")
        shutil.copy2(ROOT / "scripts" / "settings_runtime_verify.py", repo / "scripts" / "settings_runtime_verify.py")
        subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "Test User"], check=True)
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", origin], check=True)
        subprocess.run(
            ["git", "-C", str(repo), "add", "scripts/uaro.py", "scripts/settings_runtime_verify.py"],
            check=True,
        )
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "fixture"], check=True)
        return repo

    def build(self, repo: Path, destination: Path, python_path: str | Path | None = None) -> dict:
        return runtime.build_settings_runtime(repo, destination, python_path or sys.executable)

    def build_from_root(self, parent: Path, destination: Path, python_path: str | Path | None = None) -> dict:
        return self.build(self.make_repo_fixture(parent), destination, python_path)

    def make_fake_interpreter(
        self,
        parent: Path,
        name: str,
        version: tuple[int, int, int] = (3, 12, 0),
        mode: str = "valid",
        executable: bool = True,
    ) -> Path:
        path = parent / name
        path.write_text(
            f"#!{sys.executable}\n"
            "import json\n"
            "import sys\n"
            "from pathlib import Path\n"
            "config = json.loads(Path(str(Path(__file__)) + '.json').read_text())\n"
            "if len(sys.argv) < 2 or sys.argv[1] != '-c':\n"
            "    raise SystemExit(2)\n"
            "if config['mode'] == 'fail':\n"
            "    raise SystemExit(9)\n"
            "if config['mode'] == 'malformed':\n"
            "    print('not-json')\n"
            "    raise SystemExit(0)\n"
            "print(json.dumps({'implementation': 'CPython', 'version': config['version'], 'executable': sys.executable}, sort_keys=True))\n",
            encoding="utf-8",
        )
        path.with_name(path.name + ".json").write_text(
            json.dumps({"mode": mode, "version": list(version)}), encoding="utf-8"
        )
        path.chmod(0o755 if executable else 0o644)
        return path

    def make_non_python(self, parent: Path, name: str = "not-python") -> Path:
        path = parent / name
        path.write_text("#!/bin/sh\necho not-python\n", encoding="utf-8")
        path.chmod(0o755)
        return path

    def test_valid_artifact_and_byte_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "uaro-runtime"
            built = self.build_from_root(root, destination)
            verified = runtime.verify_settings_runtime(destination)
            self.assertEqual(built["result"], "success")
            self.assertEqual(verified["result"], "PASS")
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            self.assertEqual(set(manifest), runtime.REQUIRED_MANIFEST_KEYS)
            self.assertEqual(manifest["canonical_source"], "scripts/uaro.py")
            self.assertEqual(manifest["executor_relpath"], "uaro.py")
            self.assertEqual(manifest["verifier_relpath"], "settings_runtime_verify.py")
            self.assertEqual(manifest["interface_version"], runtime.INTERFACE_VERSION)
            self.assertEqual(manifest["schema_version"], runtime.SCHEMA_VERSION)
            self.assertEqual(manifest["python"]["invocation_path"], str(Path(sys.executable).absolute()))
            self.assertEqual(manifest["python"]["minimum_version"], {"major": 3, "minor": 10, "micro": 0})
            self.assertEqual(
                {path.name for path in destination.iterdir()},
                {"uaro.py", "settings_runtime_verify.py", "MANIFEST.json"},
            )
            self.assertEqual((destination / "uaro.py").read_bytes(), (ROOT / "scripts/uaro.py").read_bytes())
            self.assertEqual(
                (destination / "settings_runtime_verify.py").read_bytes(),
                (ROOT / "scripts/settings_runtime_verify.py").read_bytes(),
            )
            self.assertEqual(
                built["executor_sha256"], hashlib.sha256((destination / "uaro.py").read_bytes()).hexdigest()
            )
            self.assertEqual(
                built["verifier_sha256"],
                hashlib.sha256((destination / "settings_runtime_verify.py").read_bytes()).hexdigest(),
            )

    def test_deployed_verifier_cli_passes_without_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "runtime"
            self.build_from_root(root, destination)
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            shutil.rmtree(root / "canonical-repo")
            completed = subprocess.run(
                [manifest["python"]["invocation_path"], str(destination / "settings_runtime_verify.py"), str(destination)],
                cwd=temp,
                env={"PATH": os.environ.get("PATH", ""), "PYTHONPATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            result = json.loads(completed.stdout)
            self.assertEqual(result["result"], "PASS")
            self.assertTrue(result["executor_verified"])
            self.assertTrue(result["verifier_verified"])
            self.assertTrue(result["python_verified"])

    def test_explicit_supported_python_path_generates_and_validates(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            interpreter = self.make_fake_interpreter(root, "python3-contract")
            destination = root / "runtime"
            self.build_from_root(root, destination, interpreter)
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            evidence = runtime.validate_python_runtime(manifest["python"])
            self.assertTrue(evidence["usable"])
            self.assertEqual(evidence["invocation_path"], str(interpreter.absolute()))
            self.assertEqual(evidence["observed_version"], {"major": 3, "minor": 12, "micro": 0})

    def test_invalid_explicit_interpreter_paths_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            cases = {
                "relative": "python3",
                "missing": str(root / "missing-python"),
            }
            for name, path in cases.items():
                with self.subTest(name=name):
                    with self.assertRaises(runtime.PythonRuntimeError):
                        self.build(repo, root / name, path)

            non_executable = self.make_fake_interpreter(root, "non-executable", executable=False)
            with self.assertRaises(runtime.PythonRuntimeError):
                self.build(repo, root / "non-executable-runtime", non_executable)

            non_python = self.make_non_python(root)
            with self.assertRaises(runtime.PythonRuntimeError):
                self.build(repo, root / "non-python-runtime", non_python)

    def test_old_or_non_python_versions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            for name, version in (("python2", (2, 7, 18)), ("python39", (3, 9, 19))):
                interpreter = self.make_fake_interpreter(root, name, version=version)
                with self.subTest(name=name), self.assertRaises(runtime.PythonRuntimeError):
                    self.build(repo, root / f"{name}-runtime", interpreter)

    def test_probe_failure_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            interpreter = self.make_fake_interpreter(root, "probe-failure", mode="fail")
            with self.assertRaises(runtime.PythonRuntimeError):
                self.build(repo, root / "runtime", interpreter)
            malformed = self.make_fake_interpreter(root, "probe-malformed", mode="malformed")
            with self.assertRaises(runtime.PythonRuntimeError):
                self.build(repo, root / "malformed-runtime", malformed)

    def test_malformed_python_contract_is_rejected_without_running_interpreter(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp) / "runtime"
            root = Path(temp)
            self.build_from_root(root, destination)
            manifest_path = destination / "MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["python"] = {"invocation_path": "python3"}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaises(runtime.SettingsRuntimeVerificationError):
                runtime.verify_settings_runtime(destination)
            completed = subprocess.run(
                [sys.executable, str(destination / "settings_runtime_verify.py"), str(destination)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(json.loads(completed.stdout)["result"], "BLOCK")

    def test_supported_upgrade_at_same_invocation_path_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            interpreter = self.make_fake_interpreter(root, "stable-python", version=(3, 12, 0))
            destination = root / "runtime"
            self.build_from_root(root, destination, interpreter)
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            interpreter.with_name(interpreter.name + ".json").write_text(
                json.dumps({"mode": "valid", "version": [3, 13, 1]}), encoding="utf-8"
            )
            evidence = runtime.validate_python_runtime(manifest["python"])
            self.assertEqual(evidence["observed_version"], {"major": 3, "minor": 13, "micro": 1})

    def test_incompatible_upgrade_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            interpreter = self.make_fake_interpreter(root, "stable-python", version=(3, 12, 0))
            destination = root / "runtime"
            self.build_from_root(root, destination, interpreter)
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            interpreter.with_name(interpreter.name + ".json").write_text(
                json.dumps({"mode": "valid", "version": [3, 9, 19]}), encoding="utf-8"
            )
            with self.assertRaises(runtime.PythonRuntimeError):
                runtime.validate_python_runtime(manifest["python"])

    def test_missing_runtime_has_no_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            valid = self.make_fake_interpreter(root, "path-python")
            contract = {
                "invocation_path": str(root / "deleted-python"),
                "resolved_path": str(root / "deleted-python"),
                "version": {"major": 3, "minor": 12, "micro": 0},
                "minimum_version": {"major": 3, "minor": 10, "micro": 0},
            }
            with mock.patch.dict(os.environ, {"PATH": str(root)}, clear=False):
                with self.assertRaises(runtime.PythonRuntimeError):
                    runtime.validate_python_runtime(contract)
            self.assertTrue(valid.exists())

    def test_deployed_verifier_has_no_python_path_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            destination = root / "runtime"
            self.build_from_root(root, destination)
            manifest_path = destination / "MANIFEST.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["python"]["invocation_path"] = str(root / "missing-python")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            completed = subprocess.run(
                [sys.executable, str(destination / "settings_runtime_verify.py"), str(destination)],
                env={"PATH": str(root), "PYTHONPATH": ""},
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(json.loads(completed.stdout)["result"], "BLOCK")

    def test_repository_independence_after_source_disappears(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            destination = root / "runtime"
            self.build(repo, destination)
            manifest = json.loads((destination / "MANIFEST.json").read_text(encoding="utf-8"))
            shutil.rmtree(repo)
            self.assertEqual(runtime.verify_settings_runtime(destination)["result"], "PASS")
            self.assertTrue(runtime.validate_python_runtime(manifest["python"])["usable"])

    def test_tamper_and_missing_artifacts_fail_closed(self) -> None:
        cases = (
            "tamper",
            "missing-executor",
            "missing-verifier",
            "tamper-verifier",
            "missing-manifest",
            "malformed-manifest",
            "digest",
            "verifier-digest",
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                destination = root / "runtime"
                self.build_from_root(root, destination)
                if case == "tamper":
                    path = destination / "uaro.py"
                    data = bytearray(path.read_bytes())
                    data[0] ^= 1
                    path.write_bytes(data)
                elif case == "missing-executor":
                    (destination / "uaro.py").unlink()
                elif case == "missing-verifier":
                    (destination / "settings_runtime_verify.py").unlink()
                elif case == "tamper-verifier":
                    (destination / "settings_runtime_verify.py").write_bytes(
                        (destination / "settings_runtime_verify.py").read_bytes() + b"\n"
                    )
                elif case == "missing-manifest":
                    (destination / "MANIFEST.json").unlink()
                elif case == "malformed-manifest":
                    (destination / "MANIFEST.json").write_text("{", encoding="utf-8")
                elif case == "digest":
                    manifest_path = destination / "MANIFEST.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["executor_sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                else:
                    manifest_path = destination / "MANIFEST.json"
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                    manifest["verifier_sha256"] = "0" * 64
                    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(runtime.SettingsRuntimeVerificationError):
                    runtime.verify_settings_runtime(destination)
                completed = subprocess.run(
                    [sys.executable, str(destination / "settings_runtime_verify.py"), str(destination)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                if case != "missing-verifier":
                    self.assertEqual(json.loads(completed.stdout)["result"], "BLOCK")

    def test_manifest_schema_path_and_identity_validation(self) -> None:
        mutations = {
            "schema_version": runtime.SCHEMA_VERSION + 1,
            "interface_version": runtime.INTERFACE_VERSION + 1,
            "executor_relpath": "elsewhere/uaro.py",
            "canonical_source": "other.py",
            "source_commit": "not-a-commit",
            "executor_sha256": "not-a-digest",
            "verifier_relpath": "elsewhere/settings_runtime_verify.py",
            "verifier_sha256": "not-a-digest",
        }
        for key, value in mutations.items():
            with self.subTest(key=key), tempfile.TemporaryDirectory() as temp:
                root = Path(temp)
                destination = Path(temp) / "runtime"
                self.build_from_root(root, destination)
                manifest_path = destination / "MANIFEST.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                manifest[key] = value
                manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
                with self.assertRaises(runtime.SettingsRuntimeVerificationError):
                    runtime.verify_settings_runtime(destination)
                completed = subprocess.run(
                    [sys.executable, str(destination / "settings_runtime_verify.py"), str(destination)],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                self.assertNotEqual(completed.returncode, 0)
                self.assertEqual(json.loads(completed.stdout)["result"], "BLOCK")

    def test_dirty_canonical_source_blocks_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            source = repo / "scripts/uaro.py"
            source.write_bytes(source.read_bytes() + b"\n# dirty\n")
            with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "dirty"):
                self.build(repo, root / "runtime")

    def test_dirty_canonical_verifier_blocks_generation(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            source = repo / "scripts/settings_runtime_verify.py"
            source.write_bytes(source.read_bytes() + b"\n# dirty\n")
            with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "settings_runtime_verify.py.*dirty"):
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
            repo = self.make_repo_fixture(root)
            self.build(repo, first)
            self.build(repo, second)
            self.assertEqual((first / "uaro.py").read_bytes(), (second / "uaro.py").read_bytes())
            self.assertEqual((first / "MANIFEST.json").read_bytes(), (second / "MANIFEST.json").read_bytes())

    def test_changing_generation_interpreter_contract_changes_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_interpreter = self.make_fake_interpreter(root, "python-first", version=(3, 12, 0))
            second_interpreter = self.make_fake_interpreter(root, "python-second", version=(3, 12, 0))
            first = root / "first"
            second = root / "second"
            repo = self.make_repo_fixture(root)
            self.build(repo, first, first_interpreter)
            self.build(repo, second, second_interpreter)
            self.assertNotEqual(
                (first / "MANIFEST.json").read_bytes(), (second / "MANIFEST.json").read_bytes()
            )

    def test_failed_generation_leaves_no_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            destination = root / "runtime"
            with mock.patch.object(
                runtime.verifier,
                "verify_settings_runtime",
                side_effect=runtime.SettingsRuntimeVerificationError("forced"),
            ):
                with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "generated runtime verification failed"):
                    self.build(repo, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".runtime.*")), [])

    def test_failed_generation_rejects_non_pass_verifier_result(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            repo = self.make_repo_fixture(root)
            destination = root / "runtime"
            with mock.patch.object(runtime.verifier, "verify_settings_runtime", return_value={"result": "BLOCK"}):
                with self.assertRaisesRegex(runtime.SettingsRuntimeBuildError, "did not return PASS"):
                    self.build(repo, destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(root.glob(".runtime.*")), [])

    def test_python_contract_lists_deployed_verifier_dependencies(self) -> None:
        self.assertIn("subprocess", runtime.PYTHON_REQUIRED_MODULES)
        self.assertIn("sys", runtime.PYTHON_REQUIRED_MODULES)

    def test_verifier_is_self_contained_and_not_mutation_authority(self) -> None:
        source = (ROOT / "scripts/settings_runtime_verify.py").read_text(encoding="utf-8")
        self.assertNotIn("build_settings_runtime", source)
        self.assertNotIn("fcom apply", source)
        self.assertNotIn("savedata", source)
        self.assertIn("verifier_sha256", source)

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
