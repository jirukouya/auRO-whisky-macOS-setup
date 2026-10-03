#!/usr/bin/env python3
"""Direct adversarial tests for the AzzyAI USER_AI safety boundary."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import azzyai  # noqa: E402


def tree_bytes(root: Path) -> dict[str, object]:
    if not root.exists():
        return {"<missing>": True}
    result: dict[str, object] = {}
    for item in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        relative = item.relative_to(root).as_posix()
        if item.is_dir():
            result[relative] = "directory"
        elif item.is_file():
            result[relative] = item.read_bytes()
        else:
            result[relative] = "other"
    return result


class AzzyAiBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="azzyai-safety-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def user_ai(self, name: str = "USER_AI", files: dict[str, bytes] | None = None) -> Path:
        root = self.root / name
        root.mkdir(parents=True)
        for relative, content in (files or {}).items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return root

    def test_populated_nested_tree_is_verified_and_source_unchanged(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai", "config/M_Config.lua": b"settings"})
        before = tree_bytes(source)
        result = azzyai.backup_user_ai(source, self.root / "backup")
        self.assertEqual(result["result"], "success")
        self.assertTrue(result["backup_verified"])
        self.assertFalse(result["replacement_authorized"])
        self.assertEqual(result["comparison"]["status"], "equal")
        self.assertEqual(tree_bytes(source), before)

    def test_empty_existing_tree_is_a_valid_backup_state(self) -> None:
        source = self.user_ai()
        result = azzyai.backup_user_ai(source, self.root / "backup")
        self.assertEqual(result["source_state"], "empty")
        self.assertTrue(result["backup_verified"])

    def test_missing_source_blocks(self) -> None:
        result = azzyai.backup_user_ai(self.root / "missing", self.root / "backup")
        self.assertEqual(result["source_state"], "missing")
        self.assertFalse(result["backup_verified"])
        self.assertFalse((self.root / "backup").exists())

    def test_source_symlink_blocks(self) -> None:
        real = self.user_ai(files={"AI.lua": b"ai"})
        link = self.root / "USER_AI-link"
        link.symlink_to(real, target_is_directory=True)
        result = azzyai.backup_user_ai(link, self.root / "backup")
        self.assertEqual(result["source_state"], "unsupported")
        self.assertFalse(result["backup_verified"])

    def test_nested_symlink_blocks(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})
        (source / "link").symlink_to("AI.lua")
        result = azzyai.backup_user_ai(source, self.root / "backup")
        self.assertEqual(result["source_state"], "unsupported")
        self.assertFalse(result["backup_verified"])

    def test_destination_inside_source_blocks(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})
        result = azzyai.backup_user_ai(source, source / "backup")
        self.assertIn("inside USER_AI", result["reason"])
        self.assertFalse(result["backup_verified"])

    def test_sibling_prefix_destination_is_safe(self) -> None:
        source = self.user_ai(name="USER_AI", files={"AI.lua": b"ai"})
        result = azzyai.backup_user_ai(source, self.root / "USER_AI-backup")
        self.assertTrue(result["backup_verified"])

    def test_existing_destination_is_never_overwritten(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})
        destination = self.root / "backup"
        destination.mkdir()
        (destination / "keep").write_bytes(b"keep")
        before = tree_bytes(destination)
        result = azzyai.backup_user_ai(source, destination)
        self.assertFalse(result["backup_verified"])
        self.assertEqual(tree_bytes(destination), before)

    def test_copy_failure_blocks_even_after_partial_copy(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})

        def copy_then_fail(src: Path, dst: Path) -> bool:
            shutil.copytree(src, dst)
            return False

        result = azzyai.backup_user_ai(source, self.root / "backup", copy_fn=copy_then_fail)
        self.assertEqual(result["copy"]["status"], "failed")
        self.assertFalse(result["backup_verified"])

    def test_backup_parent_swap_during_copy_blocks_verification(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})
        parent = self.root / "backup-parent"
        parent.mkdir()
        destination = parent / "backup"
        moved_parent = self.root / "moved-backup-parent"
        external = self.root / "external-parent"

        def swap_parent(src: Path, dst: Path) -> None:
            shutil.copytree(src, dst)
            parent.rename(moved_parent)
            external.mkdir()
            parent.symlink_to(external, target_is_directory=True)

        result = azzyai.backup_user_ai(source, destination, copy_fn=swap_parent)
        self.assertFalse(result["backup_verified"])
        self.assertIn("parent changed", result["reason"])
        self.assertTrue((moved_parent / "backup" / "AI.lua").is_file())

    def test_backup_cli_blocks_if_evidence_append_fails(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})
        destination = self.root / "backup"
        original_append = azzyai._append_evidence

        def fail_append(path: Path, result: dict[str, object], phase: str) -> dict[str, object]:
            return {"status": "failed", "path": str(path), "phase": phase, "reason": "injected"}

        azzyai._append_evidence = fail_append  # type: ignore[assignment]
        try:
            output = StringIO()
            with redirect_stdout(output):
                return_code = azzyai.main(
                    [
                        "backup",
                        "--source",
                        str(source),
                        "--destination",
                        str(destination),
                    ]
                )
        finally:
            azzyai._append_evidence = original_append  # type: ignore[assignment]
        payload = json.loads(output.getvalue())
        self.assertEqual(return_code, 1)
        self.assertEqual(payload["result"], "blocked")
        self.assertTrue(payload["backup_verified"])

    def test_nonzero_copy_result_blocks_even_with_success_output(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})

        def command_like_failure(src: Path, dst: Path) -> object:
            shutil.copytree(src, dst)
            return SimpleNamespace(returncode=1, stdout="SUCCESS", stderr="failed")

        result = azzyai.backup_user_ai(source, self.root / "backup", copy_fn=command_like_failure)
        self.assertEqual(result["copy"]["status"], "failed")
        self.assertFalse(result["backup_verified"])

        result = azzyai.backup_user_ai(
            source,
            self.root / "backup-int",
            copy_fn=lambda src, dst: 1,
        )
        self.assertFalse(result["backup_verified"])
        result = azzyai.backup_user_ai(
            source,
            self.root / "backup-status",
            copy_fn=lambda src, dst: {"status": "failed", "stdout": "SUCCESS"},
        )
        self.assertFalse(result["backup_verified"])

    def test_byte_mismatch_blocks(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai"})

        def corrupt(src: Path, dst: Path) -> None:
            shutil.copytree(src, dst)
            (dst / "AI.lua").write_bytes(b"tampered")

        result = azzyai.backup_user_ai(source, self.root / "backup", copy_fn=corrupt)
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertFalse(result["backup_verified"])

    def test_missing_and_extra_entries_block(self) -> None:
        source = self.user_ai(files={"AI.lua": b"ai", "M_Config.lua": b"cfg"})

        def remove_one(src: Path, dst: Path) -> None:
            shutil.copytree(src, dst)
            (dst / "M_Config.lua").unlink()

        missing = azzyai.backup_user_ai(source, self.root / "missing", copy_fn=remove_one)
        self.assertIn("M_Config.lua", missing["comparison"]["missing"])
        self.assertFalse(missing["backup_verified"])

        def add_one(src: Path, dst: Path) -> None:
            shutil.copytree(src, dst)
            (dst / "unexpected").write_bytes(b"extra")

        extra = azzyai.backup_user_ai(source, self.root / "extra", copy_fn=add_one)
        self.assertIn("unexpected", extra["comparison"]["extra"])
        self.assertFalse(extra["backup_verified"])


class AzzyAiReplacementTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="azzyai-replace-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def tree(self, name: str, files: dict[str, bytes]) -> Path:
        root = self.root / name
        root.mkdir(parents=True)
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return root

    def authorize(self) -> tuple[dict[str, object], azzyai.ReplacementAuthorization | None, Path, Path]:
        staged = self.tree("staged", {"AI.lua": b"new", "M_Config.lua": b"new-config"})
        destination = self.tree("USER_AI", {"AI.lua": b"old", "custom.lua": b"keep"})
        result, token = azzyai.authorize_user_ai_replacement(
            staged, destination, self.root / "external-backup"
        )
        return result, token, staged, destination

    def test_replacement_requires_authorization(self) -> None:
        result = azzyai.replace_user_ai(None)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("required", result["reason"])

        spoofed = {"backup_verified": True, "replacement_authorized": True}
        result = azzyai.replace_user_ai(spoofed)  # type: ignore[arg-type]
        self.assertEqual(result["result"], "blocked")

    def test_failed_backup_never_authorizes_replacement(self) -> None:
        staged = self.tree("staged", {"AI.lua": b"new"})
        destination = self.tree("USER_AI", {"AI.lua": b"old"})
        before = tree_bytes(destination)

        def copy_then_fail(src: Path, dst: Path) -> bool:
            shutil.copytree(src, dst)
            return False

        result, token = azzyai.authorize_user_ai_replacement(
            staged, destination, self.root / "backup", copy_fn=copy_then_fail
        )
        self.assertIsNone(token)
        self.assertFalse(result["replacement_authorized"])
        blocked = azzyai.replace_user_ai(token)
        self.assertEqual(blocked["result"], "blocked")
        self.assertEqual(tree_bytes(destination), before)

    def test_backup_destination_overlapping_staged_source_blocks(self) -> None:
        staged = self.tree("staged", {"AI.lua": b"new"})
        destination = self.tree("USER_AI", {"AI.lua": b"old"})
        result, token = azzyai.authorize_user_ai_replacement(
            staged, destination, staged / "backup"
        )
        self.assertIsNone(token)
        self.assertFalse(result["replacement_authorized"])
        self.assertIn("overlaps", result["reason"])

    def test_successful_replacement_is_exact_and_preserves_previous_tree(self) -> None:
        result, token, staged, destination = self.authorize()
        self.assertIsNotNone(token)
        self.assertTrue(result["backup_verified"])
        self.assertTrue(result["replacement_authorized"])
        replaced = azzyai.replace_user_ai(token)
        self.assertEqual(replaced["result"], "success")
        self.assertTrue(replaced["replacement_verified"])
        self.assertEqual(tree_bytes(destination), tree_bytes(staged))
        previous = Path(replaced["previous"])
        self.assertTrue(previous.is_dir())
        self.assertEqual((previous / "custom.lua").read_bytes(), b"keep")

    def test_source_change_after_authorization_blocks(self) -> None:
        _, token, staged, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)
        (staged / "AI.lua").write_bytes(b"changed")
        result = azzyai.replace_user_ai(token)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("source changed", result["reason"])
        self.assertEqual(tree_bytes(destination), before)

    def test_destination_symlink_after_authorization_blocks(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        external = self.root / "external"
        external.mkdir()
        (external / "AI.lua").write_bytes(b"old")
        original = self.root / "old-user-ai"
        destination.rename(original)
        destination.symlink_to(external, target_is_directory=True)
        result = azzyai.replace_user_ai(token)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("symlink", result["reason"])
        self.assertEqual((external / "AI.lua").read_bytes(), b"old")

    def test_destination_parent_exchange_after_authorization_blocks(self) -> None:
        staged = self.tree("staged", {"AI.lua": b"new"})
        container = self.root / "container"
        container.mkdir()
        destination = container / "USER_AI"
        destination.mkdir()
        (destination / "AI.lua").write_bytes(b"old")
        result, token = azzyai.authorize_user_ai_replacement(
            staged, destination, self.root / "external-backup"
        )
        self.assertTrue(result["replacement_authorized"])
        assert token is not None
        external = self.root / "external-parent"
        external.mkdir()
        (external / "USER_AI").mkdir()
        (external / "USER_AI" / "AI.lua").write_bytes(b"external")
        moved = self.root / "moved-container"
        container.rename(moved)
        container.symlink_to(external, target_is_directory=True)
        replaced = azzyai.replace_user_ai(token)
        self.assertEqual(replaced["result"], "blocked")
        self.assertTrue(
            "identity changed" in replaced["reason"]
            or "symlink components" in replaced["reason"]
        )
        self.assertEqual((external / "USER_AI" / "AI.lua").read_bytes(), b"external")

    def test_ancestor_symlink_alias_is_rejected(self) -> None:
        staged = self.tree("staged", {"AI.lua": b"new"})
        real_parent = self.root / "real-parent"
        real_parent.mkdir()
        destination = real_parent / "USER_AI"
        destination.mkdir()
        (destination / "AI.lua").write_bytes(b"old")
        alias = self.root / "alias"
        alias.symlink_to(real_parent, target_is_directory=True)
        result, token = azzyai.authorize_user_ai_replacement(
            staged, alias / "USER_AI", self.root / "backup"
        )
        self.assertIsNone(token)
        self.assertFalse(result["replacement_authorized"])
        self.assertIn("symlink components", result["reason"])

    def test_verified_backup_change_after_authorization_blocks(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        backup = token.backup
        (backup / "AI.lua").write_bytes(b"tampered-backup")
        before = tree_bytes(destination)
        result = azzyai.replace_user_ai(token)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("backup", result["reason"])
        self.assertEqual(tree_bytes(destination), before)

    def test_destination_change_after_authorization_blocks(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)
        (destination / "new-user-file").write_bytes(b"changed")
        result = azzyai.replace_user_ai(token)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("destination changed", result["reason"])
        self.assertEqual((destination / "new-user-file").read_bytes(), b"changed")
        self.assertNotEqual(tree_bytes(destination), before)

    def test_replacement_copy_failure_leaves_destination_unchanged(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)

        def copy_then_fail(src: Path, dst: Path) -> bool:
            shutil.copytree(src, dst)
            return False

        result = azzyai.replace_user_ai(token, copy_fn=copy_then_fail)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("USER_AI was not changed", result["reason"])
        self.assertTrue(result["staging_cleaned"])
        self.assertEqual(tree_bytes(destination), before)

    def test_replacement_staging_mismatch_blocks(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)

        def corrupt(src: Path, dst: Path) -> None:
            shutil.copytree(src, dst)
            (dst / "AI.lua").write_bytes(b"tampered")

        result = azzyai.replace_user_ai(token, copy_fn=corrupt)
        self.assertEqual(result["result"], "blocked")
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertTrue(result["staging_cleaned"])
        self.assertEqual(tree_bytes(destination), before)

    def test_nonzero_replacement_result_blocks_even_with_success_output(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)

        def command_like_failure(src: Path, dst: Path) -> object:
            shutil.copytree(src, dst)
            return SimpleNamespace(returncode=1, stdout="SUCCESS", stderr="failed")

        result = azzyai.replace_user_ai(token, copy_fn=command_like_failure)
        self.assertEqual(result["result"], "blocked")
        self.assertEqual(result["copy"]["status"], "failed")
        self.assertEqual(tree_bytes(destination), before)

    def test_cli_emits_structured_success(self) -> None:
        staged = self.tree("staged", {"AI.lua": b"new"})
        destination = self.tree("USER_AI", {"AI.lua": b"old"})
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "azzyai.py"),
                "replace",
                "--source",
                str(staged),
                "--destination",
                str(destination),
                "--backup",
                str(self.root / "backup"),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0, process.stderr)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["replacement_verified"])
        self.assertTrue(payload["authorization"]["backup_verified"])
        self.assertEqual(payload["evidence"]["status"], "succeeded")
        evidence_path = Path(payload["evidence"]["path"])
        self.assertEqual(evidence_path.stat().st_mode & 0o777, 0o600)
        records = [json.loads(line) for line in evidence_path.read_text().splitlines()]
        self.assertEqual(
            [record["phase"] for record in records],
            ["replacement-authorized", "replacement-complete"],
        )
        self.assertEqual([record["result"] for record in records], ["authorized", "success"])
        for record in records:
            self.assertEqual(record["schema_version"], 1)
            self.assertIn("descriptive-only", record["evidence_scope"])

    def test_evidence_path_overlap_blocks_before_exchange(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)
        result = azzyai.replace_user_ai(token, evidence_path=destination / "evidence.jsonl")
        self.assertEqual(result["result"], "blocked")
        self.assertIn("evidence path", result["reason"])
        self.assertEqual(tree_bytes(destination), before)

    def test_evidence_write_failure_blocks_before_exchange(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)
        parent_file = self.root / "not-a-directory"
        parent_file.write_bytes(b"file")
        result = azzyai.replace_user_ai(
            token, evidence_path=parent_file / "evidence.jsonl"
        )
        self.assertEqual(result["result"], "blocked")
        self.assertIn("evidence could not be persisted", result["reason"])
        self.assertTrue(result["staging_cleaned"])
        self.assertEqual(tree_bytes(destination), before)

    def test_completion_evidence_failure_restores_original_tree(self) -> None:
        _, token, _, destination = self.authorize()
        assert token is not None
        before = tree_bytes(destination)
        evidence_path = self.root / "evidence.jsonl"
        original_append = azzyai._append_evidence

        def fail_completion(path: Path, result: dict[str, object], phase: str) -> dict[str, object]:
            if phase == "replacement-complete":
                persisted = original_append(path, result, phase)
                persisted["status"] = "failed"
                persisted["reason"] = "injected after write"
                return persisted
            return original_append(path, result, phase)

        azzyai._append_evidence = fail_completion  # type: ignore[assignment]
        try:
            result = azzyai.replace_user_ai(token, evidence_path=evidence_path)
        finally:
            azzyai._append_evidence = original_append  # type: ignore[assignment]
        self.assertEqual(result["result"], "blocked")
        self.assertFalse(result["replacement_verified"])
        self.assertTrue(result["restored"])
        self.assertEqual(tree_bytes(destination), before)
        self.assertFalse((destination.parent / ".USER_AI.azzyai-previous").exists())
        self.assertFalse((destination.parent / ".USER_AI.azzyai-staging").exists())
        records = [json.loads(line) for line in evidence_path.read_text().splitlines()]
        self.assertEqual(
            [record["phase"] for record in records],
            ["replacement-authorized", "replacement-complete", "replacement-rollback"],
        )
        self.assertEqual(records[-1]["result"], "blocked")


if __name__ == "__main__":
    unittest.main()
