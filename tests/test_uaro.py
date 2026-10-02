#!/usr/bin/env python3
"""Direct tests for the deterministic FCOM spike implementation."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
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


def tree_snapshot(root: Path) -> dict[str, object]:
    if not root.exists():
        return {"<missing>": True}
    snapshot: dict[str, object] = {}
    for item in sorted(root.rglob("*"), key=lambda path: path.as_posix()):
        relative = item.relative_to(root).as_posix()
        if item.is_dir():
            snapshot[relative] = "directory"
        elif item.is_file():
            snapshot[relative] = item.read_bytes()
        else:
            snapshot[relative] = "other"
    return snapshot


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


class SavedataBackupTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="uaro-savedata-core-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def game_with_savedata(self, files: dict[str, bytes] | None = None) -> Path:
        game = self.root / "game"
        source = game / "savedata"
        source.mkdir(parents=True)
        for relative, content in (files or {}).items():
            path = source / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        return game

    def assert_verified(self, result: dict[str, object], source_state: str) -> None:
        self.assertEqual(result["result"], "success")
        self.assertEqual(result["source_state"], source_state)
        self.assertTrue(result["backup_verified"])
        self.assertFalse(result["deletion_authority"])
        self.assertEqual(result["copy"]["status"], "succeeded")
        self.assertEqual(result["comparison"]["status"], "equal")

    def test_nonempty_external_backup_is_verified_and_source_unchanged(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = self.root / "savedata-backup"
        before = tree_snapshot(game)
        result = uaro.backup_savedata(game, destination)
        self.assert_verified(result, "populated")
        self.assertEqual(tree_snapshot(game), before)
        self.assertEqual((destination / "slot.dat").read_bytes(), b"save")

    def test_empty_existing_savedata_is_preserved(self) -> None:
        game = self.game_with_savedata()
        result = uaro.backup_savedata(game, self.root / "empty-backup")
        self.assert_verified(result, "empty")

    def test_missing_savedata_is_distinguished(self) -> None:
        game = self.root / "missing-game"
        game.mkdir()
        destination = self.root / "missing-backup"
        result = uaro.backup_savedata(game, destination)
        self.assertEqual(result["source_state"], "missing")
        self.assertFalse(result["backup_verified"])
        self.assertFalse(destination.exists())

    def test_destination_inside_source_is_blocked(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = game / "savedata" / "backup"
        result = uaro.backup_savedata(game, destination)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("inside GAME_DIR", result["reason"])
        self.assertFalse(destination.exists())

    def test_destination_elsewhere_inside_game_is_blocked(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = game / "backup"
        result = uaro.backup_savedata(game, destination)
        self.assertEqual(result["result"], "blocked")
        self.assertFalse(destination.exists())

    def test_resolved_destination_inside_game_is_blocked(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        (game / "alias").symlink_to(game, target_is_directory=True)
        destination = game / "alias" / "resolved-backup"
        result = uaro.backup_savedata(game, destination)
        self.assertEqual(result["result"], "blocked")
        self.assertIn("inside GAME_DIR", result["reason"])

    def test_destination_with_game_prefix_but_outside_game_is_allowed(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = self.root / "game-sibling-backup"
        result = uaro.backup_savedata(game, destination)
        self.assert_verified(result, "populated")

    def test_existing_destination_is_rejected_and_preserved(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = self.root / "existing-backup"
        destination.mkdir()
        (destination / "old").write_bytes(b"keep")
        before = tree_snapshot(destination)
        result = uaro.backup_savedata(game, destination)
        self.assertEqual(result["result"], "blocked")
        self.assertFalse(result["backup_verified"])
        self.assertEqual(tree_snapshot(destination), before)

    def test_content_mismatch_is_not_verified(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})

        def corrupt_copy(source: Path, destination: Path) -> None:
            shutil.copytree(source, destination)
            (destination / "slot.dat").write_bytes(b"changed")

        result = uaro.backup_savedata(game, self.root / "mismatch", copy_fn=corrupt_copy)
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertFalse(result["backup_verified"])

    def test_missing_copied_file_is_not_verified(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save", "other.dat": b"other"})

        def missing_copy(source: Path, destination: Path) -> None:
            shutil.copytree(source, destination)
            (destination / "other.dat").unlink()

        result = uaro.backup_savedata(game, self.root / "missing-file", copy_fn=missing_copy)
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertIn("other.dat", result["comparison"]["missing"])
        self.assertFalse(result["backup_verified"])

    def test_extra_copied_file_is_not_verified(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})

        def extra_copy(source: Path, destination: Path) -> None:
            shutil.copytree(source, destination)
            (destination / "unexpected.dat").write_bytes(b"extra")

        result = uaro.backup_savedata(game, self.root / "extra-file", copy_fn=extra_copy)
        self.assertEqual(result["comparison"]["status"], "mismatch")
        self.assertIn("unexpected.dat", result["comparison"]["extra"])
        self.assertFalse(result["backup_verified"])

    def test_failed_copy_after_matching_files_never_verifies(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        before = tree_snapshot(game)

        def copy_then_fail(source: Path, destination: Path) -> bool:
            shutil.copytree(source, destination)
            return False

        result = uaro.backup_savedata(game, self.root / "failed-copy", copy_fn=copy_then_fail)
        self.assertEqual(result["copy"]["status"], "failed")
        self.assertEqual(result["comparison"]["status"], "not-run")
        self.assertFalse(result["backup_verified"])
        self.assertFalse(result["deletion_authority"])
        self.assertEqual(tree_snapshot(game), before)

    def test_source_remains_and_backup_has_no_deletion_operation(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        marker = game / "keep-me"
        marker.write_text("original")
        result = uaro.backup_savedata(game, self.root / "backup")
        self.assertTrue(result["backup_verified"])
        self.assertTrue(marker.exists())
        self.assertTrue((game / "savedata" / "slot.dat").exists())

    def test_unsupported_source_entry_fails_closed(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        (game / "savedata" / "link").symlink_to("slot.dat")
        result = uaro.backup_savedata(game, self.root / "unsupported")
        self.assertEqual(result["source_state"], "unsupported")
        self.assertFalse(result["backup_verified"])

    def test_backup_cli_emits_structured_success(self) -> None:
        game = self.game_with_savedata({"slot.dat": b"save"})
        destination = self.root / "cli-backup"
        process = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "uaro.py"),
                "backup",
                "savedata",
                "--game-dir",
                str(game),
                "--destination",
                str(destination),
            ],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0)
        payload = json.loads(process.stdout)
        self.assertTrue(payload["backup_verified"])
        self.assertFalse(payload["deletion_authority"])


class InspectTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="uaro-inspect-core-")
        self.root = Path(self.temp.name)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def make_game(self, name: str = "game") -> Path:
        game = self.root / name
        game.mkdir()
        return game

    def inspect(self, game: Path, apps: Path | None = None) -> dict[str, object]:
        return uaro.inspect_install(game, apps)

    def test_missing_game_dir_is_structurally_reported(self) -> None:
        result = self.inspect(self.root / "missing-game")
        self.assertTrue(result["result"] == "success")
        self.assertFalse(result["evidence"]["game_dir_exists"])
        self.assertEqual(result["evidence"]["savedata"]["state"], "missing")
        self.assertEqual(result["evidence"]["fcom"]["state"], "UNKNOWN")
        self.assertFalse(result["mutation"])
        self.assertEqual(result["execution"], "UNCONFIRMED")

    def test_explicit_game_structural_files_are_reported(self) -> None:
        game = self.make_game()
        (game / "uaRO.exe").write_bytes(b"game")
        (game / "dinput.ini").write_text("config")
        (game / "savedata").mkdir()
        (game / "savedata" / "OptionInfo.lua").write_text("options")
        result = self.inspect(game)
        evidence = result["evidence"]
        self.assertTrue(evidence["game_dir_exists"])
        self.assertTrue(evidence["uaro_exe_exists"])
        self.assertFalse(evidence["setup_exe_exists"])
        self.assertTrue(evidence["optioninfo_lua_exists"])
        self.assertTrue(evidence["dinput_ini_exists"])
        self.assertEqual(evidence["savedata"]["state"], "populated")

    def test_fcom_states_reuse_the_production_classifier(self) -> None:
        for name, site_a, site_b, expected in (
            ("unpatched", uaro.A_UNPATCHED, uaro.B_UNPATCHED, "UNPATCHED"),
            ("patched", uaro.A_PATCHED, uaro.B_PATCHED, "PATCHED"),
            ("unknown", b"\x00", uaro.B_UNPATCHED, "UNKNOWN"),
        ):
            with self.subTest(name=name):
                game = self.make_game("game-" + name)
                (game / "setup.exe").write_bytes(fixture_binary(site_a, site_b))
                result = self.inspect(game)
                self.assertEqual(result["evidence"]["fcom"]["state"], expected)

    def test_savedata_missing_empty_and_populated_states(self) -> None:
        cases = (
            ("missing", None, "missing"),
            ("empty", {}, "empty"),
            ("populated", {"slot.dat": b"save"}, "populated"),
        )
        for name, files, expected in cases:
            with self.subTest(name=name):
                game = self.make_game("game-" + name)
                if files is not None:
                    savedata = game / "savedata"
                    savedata.mkdir()
                    for relative, content in files.items():
                        (savedata / relative).write_bytes(content)
                result = self.inspect(game)
                self.assertEqual(result["evidence"]["savedata"]["state"], expected)

    def test_launcher_requiredness_and_optional_game(self) -> None:
        for missing in (None, "Patcher", "Settings"):
            with self.subTest(missing=missing):
                game = self.make_game("game-" + (missing or "all"))
                apps = self.root / ("apps-" + (missing or "all"))
                apps.mkdir()
                for name in ("UaRO Patcher.app", "UaRO Settings.app"):
                    if missing and name == "UaRO " + missing + ".app":
                        continue
                    (apps / name).mkdir()
                result = self.inspect(game, apps)
                launcher = result["apps"]
                self.assertTrue(launcher["UaRO Patcher.app"]["required"])
                self.assertTrue(launcher["UaRO Settings.app"]["required"])
                self.assertFalse(launcher["UaRO Game.app"]["required"])
                self.assertFalse(launcher["UaRO Game.app"]["exists"])
                if missing:
                    self.assertFalse(launcher["UaRO " + missing + ".app"]["exists"])

    def test_inspect_fixture_is_unchanged_and_makes_no_authority_claim(self) -> None:
        game = self.make_game()
        (game / "uaRO.exe").write_bytes(b"game")
        (game / "savedata").mkdir()
        (game / "savedata" / "slot.dat").write_bytes(b"save")
        apps = self.root / "apps"
        apps.mkdir()
        (apps / "UaRO Patcher.app").mkdir()
        (apps / "UaRO Settings.app").mkdir()
        before = tree_snapshot(self.root)
        result = self.inspect(game, apps)
        self.assertEqual(tree_snapshot(self.root), before)
        self.assertFalse(result["mutation"])
        self.assertFalse(result["deletion_authority"])
        self.assertEqual(result["evidence_scope"], "explicit structural facts only")
        self.assertEqual(result["execution"], "UNCONFIRMED")

    def test_inspect_cli_emits_structured_json(self) -> None:
        game = self.make_game()
        process = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "uaro.py"), "inspect", "--game-dir", str(game)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(process.returncode, 0)
        payload = json.loads(process.stdout)
        self.assertEqual(payload["operation"], "inspect")
        self.assertFalse(payload["mutation"])


if __name__ == "__main__":
    unittest.main()
