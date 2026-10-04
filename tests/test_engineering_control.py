#!/usr/bin/env python3
"""Direct tests for the evidence-only Phase 0 control plane."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import engineering_control as control  # noqa: E402


def git(repo: Path, *args: str) -> str:
    proc = subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True, text=True)
    return proc.stdout.strip()


def commit(repo: Path, message: str) -> str:
    git(repo, "add", "tracked.txt")
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "commit",
            "-m",
            message,
        ],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout and git(repo, "rev-parse", "HEAD")


class EngineeringControlTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="uaro-control-plane-")
        self.root = Path(self.temp.name) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "remote", "add", "origin", control.CANONICAL_ORIGIN)
        (self.root / "tracked.txt").write_text("one\n")
        self.parent = commit(self.root, "parent")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def state(self, **overrides: object) -> dict[str, object]:
        value: dict[str, object] = {
            "PROGRAM": control.PROGRAM,
            "EXPECTED_PARENT": self.parent,
            "EXPECTED_BRANCH": "main",
            "EXPECTED_ORIGIN": control.CANONICAL_ORIGIN,
            "AUTHORIZED_FILES": ["allowed.txt"],
            "PHASE_STATE": "INSPECTING",
            "VERIFIED_HEADS": [],
        }
        value.update(overrides)
        return value

    def test_snapshot_is_read_only_and_reports_origin_head_and_clean_state(self) -> None:
        result = control.snapshot(self.root)
        self.assertEqual(result["origin"], control.CANONICAL_ORIGIN)
        self.assertEqual(result["head"], self.parent)
        self.assertEqual(result["dirty_paths"], [])
        self.assertFalse(result["mutation"])
        self.assertEqual(result["authority"], "evidence-only")

    def test_reconcile_exact_checkpoint(self) -> None:
        result = control.reconcile(self.root, self.state())
        self.assertEqual(result["classification"], "EXACT_CHECKPOINT")
        self.assertEqual(result["result"], "success")

    def test_reconcile_scoped_in_progress_child(self) -> None:
        (self.root / "allowed.txt").write_text("scoped\n")
        result = control.reconcile(
            self.root,
            self.state(PHASE_STATE="IN_PROGRESS"),
        )
        self.assertEqual(result["classification"], "SCOPED_IN_PROGRESS_CHILD")
        self.assertEqual(result["result"], "success")

    def test_reconcile_unrelated_dirty_state_blocks(self) -> None:
        (self.root / "unrelated.txt").write_text("do not touch\n")
        result = control.reconcile(
            self.root,
            self.state(PHASE_STATE="IN_PROGRESS"),
        )
        self.assertEqual(result["classification"], "UNRELATED_DIRTY_STATE")
        self.assertEqual(result["result"], "blocked")

    def test_reconcile_wrong_branch_identity_blocks(self) -> None:
        git(self.root, "checkout", "-q", "-b", "other")
        result = control.reconcile(
            self.root,
            self.state(EXPECTED_BRANCH="main"),
        )
        self.assertEqual(result["classification"], "AMBIGUOUS_STATE")
        self.assertEqual(result["result"], "blocked")

    def test_reconcile_newer_descendant_requires_explicit_verification(self) -> None:
        (self.root / "tracked.txt").write_text("two\n")
        newer = commit(self.root, "newer")
        candidate = control.reconcile(self.root, self.state())
        self.assertEqual(candidate["result"], "blocked")
        self.assertEqual(candidate["candidate_classification"], "NEWER_VERIFIED_DESCENDANT")
        verified = control.reconcile(
            self.root,
            self.state(VERIFIED_HEADS=[newer]),
        )
        self.assertEqual(verified["classification"], "NEWER_VERIFIED_DESCENDANT")
        self.assertEqual(verified["result"], "success")

    def test_reconcile_missing_prompt_checkpoint_fails_closed(self) -> None:
        missing = "02f46de34d5699c046f4039467d756f969b5cb22"
        with self.assertRaises(control.ControlPlaneError):
            control.reconcile(self.root, self.state(EXPECTED_PARENT=missing))

    def test_reconcile_malformed_verified_heads_fails_closed(self) -> None:
        with self.assertRaises(control.ControlPlaneError):
            control.reconcile(self.root, self.state(VERIFIED_HEADS="not-a-list"))

    def test_reconcile_noncanonical_origin_fails_closed(self) -> None:
        git(self.root, "remote", "set-url", "origin", "https://example.invalid/wrong.git")
        with self.assertRaises(control.ControlPlaneError):
            control.reconcile(self.root, self.state())

    def test_state_cache_must_live_outside_repository(self) -> None:
        args = type(
            "Args",
            (),
            {
                "repo": str(self.root),
                "state_file": str(self.root / "state.json"),
                "program_goal": "goal",
                "phase": "PHASE_0",
                "phase_state": "INSPECTING",
                "expected_parent": None,
                "last_verified_head": None,
                "authorized_file": [],
                "test_summary": "",
                "next_action": "inspect",
            },
        )()
        with self.assertRaises(control.ControlPlaneError):
            control.init_state(args)

    def test_envelope_rejects_head_mismatch_and_authority_overlap(self) -> None:
        envelope = {
            "PROGRAM": control.PROGRAM,
            "PHASE_ID": "PHASE_0",
            "REPOSITORY": str(self.root.resolve()),
            "ORIGIN": control.CANONICAL_ORIGIN,
            "BRANCH": "main",
            "PARENT_HEAD": self.parent,
            "CURRENT_HEAD": "0" * 40,
            "GOAL": "goal",
            "AUTHORIZED_FILES": ["allowed.txt"],
            "AUTHORIZED_CAPABILITIES": ["READ"],
            "FORBIDDEN_FILES": ["allowed.txt"],
            "FORBIDDEN_CAPABILITIES": ["READ"],
            "FROZEN_INVARIANTS": ["invariant"],
            "EXPECTED_MUTATIONS": [],
            "REQUIRED_EVIDENCE": ["evidence"],
            "REQUIRED_TESTS": ["tests"],
            "INDEPENDENT_VERIFICATION": ["verifier"],
            "ROLLBACK_BOUNDARY": "local commit",
            "TERMINAL_STATES": sorted(control.TERMINAL_STATES),
            "WORKTREE_POLICY": "CLEAN_REQUIRED",
        }
        result = control.validate_envelope(self.root, envelope)
        self.assertEqual(result["result"], "blocked")
        self.assertFalse(result["valid"])
        self.assertTrue(any("overlap" in error for error in result["errors"]))
        self.assertTrue(any("CURRENT_HEAD" in error for error in result["errors"]))

    def test_envelope_accepts_complete_current_envelope(self) -> None:
        envelope = {
            "PROGRAM": control.PROGRAM,
            "PHASE_ID": "PHASE_0",
            "REPOSITORY": str(self.root.resolve()),
            "ORIGIN": control.CANONICAL_ORIGIN,
            "BRANCH": "main",
            "PARENT_HEAD": self.parent,
            "CURRENT_HEAD": self.parent,
            "GOAL": "goal",
            "AUTHORIZED_FILES": ["allowed.txt"],
            "AUTHORIZED_CAPABILITIES": ["READ"],
            "FORBIDDEN_FILES": ["SKILL.md"],
            "FORBIDDEN_CAPABILITIES": ["PUSH"],
            "FROZEN_INVARIANTS": ["deterministic routes"],
            "EXPECTED_MUTATIONS": ["control-plane files"],
            "REQUIRED_EVIDENCE": ["snapshot"],
            "REQUIRED_TESTS": ["fixture tests"],
            "INDEPENDENT_VERIFICATION": ["read-only audit"],
            "ROLLBACK_BOUNDARY": "focused local commit",
            "TERMINAL_STATES": sorted(control.TERMINAL_STATES),
            "WORKTREE_POLICY": "CLEAN_REQUIRED",
        }
        result = control.validate_envelope(self.root, envelope)
        self.assertEqual(result["result"], "success")
        self.assertTrue(result["valid"])
        self.assertFalse(result["mutation"])
