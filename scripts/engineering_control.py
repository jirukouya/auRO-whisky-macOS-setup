#!/usr/bin/env python3
"""Small, evidence-only control-plane primitives for uaRO engineering.

This module deliberately does not own installation, trust policy, mutation, or
destructive authority.  It only captures repository state, classifies that
state against an explicit runtime cache, and validates a bounded Phase
Envelope before a Root is allowed to plan work.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Any, Iterable


PROGRAM = "uaRO Verified Autonomous Engineering v1"
CANONICAL_ORIGIN = "https://github.com/jirukouya/auRO-whisky-macOS-setup.git"
TERMINAL_STATES = {
    "PHASE_COMPLETED",
    "BLOCKED_EXTERNAL",
    "NEEDS_ADJUDICATION",
    "NEEDS_USER_DECISION",
    "FAILED",
}
REQUIRED_ENVELOPE_KEYS = {
    "PROGRAM",
    "PHASE_ID",
    "REPOSITORY",
    "ORIGIN",
    "BRANCH",
    "PARENT_HEAD",
    "CURRENT_HEAD",
    "GOAL",
    "AUTHORIZED_FILES",
    "AUTHORIZED_CAPABILITIES",
    "FORBIDDEN_FILES",
    "FORBIDDEN_CAPABILITIES",
    "FROZEN_INVARIANTS",
    "EXPECTED_MUTATIONS",
    "REQUIRED_EVIDENCE",
    "REQUIRED_TESTS",
    "INDEPENDENT_VERIFICATION",
    "ROLLBACK_BOUNDARY",
    "TERMINAL_STATES",
    "WORKTREE_POLICY",
}
HEAD_RE = re.compile(r"^[0-9a-f]{40}$")


class ControlPlaneError(Exception):
    """A deterministic control-plane precondition failed."""


def _run_git(repo: Path, *args: str) -> str:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", *args],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip()
        raise ControlPlaneError(f"git {' '.join(args)} failed: {detail}")
    return proc.stdout.strip()


def _repo_root(repo: str | Path) -> Path:
    requested = Path(repo).expanduser().resolve()
    actual = Path(_run_git(requested, "rev-parse", "--show-toplevel")).resolve()
    if actual != requested:
        raise ControlPlaneError(f"repo path is not the Git root: {requested}")
    return actual


def _parse_status(repo: Path) -> list[str]:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "-z", "--untracked-files=all"],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if proc.returncode:
        detail = (proc.stderr or proc.stdout).strip()
        raise ControlPlaneError(f"git status failed: {detail}")
    raw = proc.stdout
    paths: list[str] = []
    entries = [entry for entry in raw.split("\0") if entry]
    index = 0
    while index < len(entries):
        line = entries[index]
        if len(line) < 4:
            index += 1
            continue
        path_text = line[3:]
        paths.append(path_text)
        status = line[:2]
        if "R" in status or "C" in status:
            if index + 1 < len(entries):
                paths.append(entries[index + 1])
                index += 1
        index += 1
    return paths


def _parse_worktrees(repo: Path) -> list[dict[str, str]]:
    raw = _run_git(repo, "worktree", "list", "--porcelain")
    entries: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        if key in {"worktree", "HEAD", "branch"}:
            current[key] = value
    if current:
        entries.append(current)
    return entries


def snapshot(repo: str | Path) -> dict[str, Any]:
    """Return a read-only repository snapshot suitable for reconciliation."""

    root = _repo_root(repo)
    branch = _run_git(root, "symbolic-ref", "--short", "-q", "HEAD") or "DETACHED"
    origin = _run_git(root, "remote", "get-url", "origin")
    return {
        "result": "success",
        "repo": str(root),
        "origin": origin,
        "branch": branch,
        "head": _run_git(root, "rev-parse", "HEAD"),
        "dirty_paths": _parse_status(root),
        "worktrees": _parse_worktrees(root),
        "mutation": False,
        "authority": "evidence-only",
    }


def _is_ancestor(repo: Path, older: str, newer: str) -> bool:
    environment = os.environ.copy()
    environment["GIT_OPTIONAL_LOCKS"] = "0"
    proc = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        cwd=repo,
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if proc.returncode not in (0, 1):
        detail = (proc.stderr or proc.stdout).strip()
        raise ControlPlaneError(f"git merge-base failed: {detail}")
    return proc.returncode == 0


def _path_allowed(path: str, allowed: Iterable[str]) -> bool:
    normalized = path.removeprefix("./")
    for entry in allowed:
        candidate = str(entry).removeprefix("./").rstrip("/")
        if normalized == candidate or normalized.startswith(candidate + "/"):
            return True
    return False


def _scopes_overlap(left: Iterable[str], right: Iterable[str]) -> bool:
    normalized_left = [str(value).removeprefix("./").rstrip("/") for value in left]
    normalized_right = [str(value).removeprefix("./").rstrip("/") for value in right]
    return any(
        a == b or a.startswith(b + "/") or b.startswith(a + "/")
        for a in normalized_left
        for b in normalized_right
    )


def _valid_state(state: dict[str, Any]) -> None:
    if not isinstance(state, dict):
        raise ControlPlaneError("program state must be a JSON object")
    for key in (
        "PROGRAM",
        "EXPECTED_PARENT",
        "EXPECTED_BRANCH",
        "EXPECTED_ORIGIN",
        "AUTHORIZED_FILES",
    ):
        if key not in state:
            raise ControlPlaneError(f"program state missing {key}")
    if state["PROGRAM"] != PROGRAM:
        raise ControlPlaneError("program state belongs to a different program")
    if not isinstance(state["AUTHORIZED_FILES"], list):
        raise ControlPlaneError("AUTHORIZED_FILES must be a list")
    if not isinstance(state["EXPECTED_BRANCH"], str) or not state["EXPECTED_BRANCH"]:
        raise ControlPlaneError("EXPECTED_BRANCH must be non-empty")
    if not isinstance(state["EXPECTED_ORIGIN"], str) or not state["EXPECTED_ORIGIN"]:
        raise ControlPlaneError("EXPECTED_ORIGIN must be non-empty")
    if state["EXPECTED_ORIGIN"] != CANONICAL_ORIGIN:
        raise ControlPlaneError("EXPECTED_ORIGIN does not match the canonical uaRO repository")
    verified_heads = state.get("VERIFIED_HEADS", [])
    if not isinstance(verified_heads, list) or not all(
        isinstance(head, str) and HEAD_RE.fullmatch(head) for head in verified_heads
    ):
        raise ControlPlaneError("VERIFIED_HEADS must be a list of full commit ids")


def _require_canonical_origin(current: dict[str, Any]) -> None:
    if current["origin"] != CANONICAL_ORIGIN:
        raise ControlPlaneError("repository origin does not match the canonical uaRO repository")


def reconcile(repo: str | Path, state: dict[str, Any]) -> dict[str, Any]:
    """Classify state without treating the cache as authority or mutating Git."""

    _valid_state(state)
    root = _repo_root(repo)
    current = snapshot(root)
    _require_canonical_origin(current)
    expected = state["EXPECTED_PARENT"]
    if not isinstance(expected, str) or not HEAD_RE.fullmatch(expected):
        raise ControlPlaneError("EXPECTED_PARENT must be a full 40-character commit id")

    dirty_paths = current["dirty_paths"]
    classification = "AMBIGUOUS_STATE"
    reason = "repository state does not match a safe reconciliation rule"
    candidate = None
    branch_mismatch = state.get("EXPECTED_BRANCH") not in (None, current["branch"])
    origin_mismatch = state.get("EXPECTED_ORIGIN") not in (None, current["origin"])
    if branch_mismatch or origin_mismatch:
        reason = "repository branch or origin does not match the cached identity"
    elif current["head"] == expected and not dirty_paths:
        classification = "EXACT_CHECKPOINT"
        reason = "HEAD equals the expected parent and the worktree is clean"
    elif current["head"] == expected and dirty_paths:
        phase_state = state.get("PHASE_STATE", "")
        if phase_state in {"IN_PROGRESS", "EXECUTING", "VERIFYING"} and all(
            _path_allowed(path, state["AUTHORIZED_FILES"]) for path in dirty_paths
        ):
            classification = "SCOPED_IN_PROGRESS_CHILD"
            reason = "dirty paths are limited to the active phase scope"
        else:
            classification = "UNRELATED_DIRTY_STATE"
            reason = "dirty paths are not both scoped and explicitly in progress"
    elif not dirty_paths and _is_ancestor(root, expected, current["head"]):
        candidate = "NEWER_VERIFIED_DESCENDANT"
        verified_heads = state.get("VERIFIED_HEADS", [])
        if current["head"] in verified_heads:
            classification = "NEWER_VERIFIED_DESCENDANT"
            reason = "current HEAD is an explicitly verified descendant of the parent"
        else:
            reason = "newer descendant found, but current HEAD is not in VERIFIED_HEADS"
    elif dirty_paths:
        classification = "UNRELATED_DIRTY_STATE"
        reason = "worktree is dirty and HEAD is not the expected parent"
    else:
        reason = "expected parent is not an ancestor of current HEAD"

    safe = classification in {
        "EXACT_CHECKPOINT",
        "NEWER_VERIFIED_DESCENDANT",
        "SCOPED_IN_PROGRESS_CHILD",
    }
    result: dict[str, Any] = {
        "result": "success" if safe else "blocked",
        "classification": classification,
        "reason": reason,
        "candidate_classification": candidate,
        "snapshot": current,
        "mutation": False,
        "authority": "evidence-only",
    }
    return result


def _load_json(path: str | Path) -> dict[str, Any]:
    try:
        value = json.loads(Path(path).read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ControlPlaneError(f"cannot read JSON {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ControlPlaneError(f"JSON root must be an object: {path}")
    return value


def _write_json(path: Path, value: dict[str, Any], *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise ControlPlaneError(f"refusing to overwrite existing state: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.replace(temp, path)


def _state_path_outside_repo(state_path: Path, repo: Path) -> Path:
    resolved = state_path.expanduser().resolve()
    try:
        resolved.relative_to(repo)
    except ValueError:
        return resolved
    raise ControlPlaneError("volatile program state must be outside the repository")


def init_state(args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root(args.repo)
    state_path = _state_path_outside_repo(Path(args.state_file), root)
    current = snapshot(root)
    _require_canonical_origin(current)
    value: dict[str, Any] = {
        "PROGRAM": PROGRAM,
        "PROGRAM_GOAL": args.program_goal,
        "CURRENT_PHASE": args.phase,
        "PHASE_STATE": args.phase_state,
        "EXPECTED_PARENT": args.expected_parent or current["head"],
        "EXPECTED_BRANCH": current["branch"],
        "EXPECTED_ORIGIN": current["origin"],
        "CURRENT_HEAD": current["head"],
        "LAST_VERIFIED_HEAD": args.last_verified_head,
        "VERIFIED_HEADS": [args.last_verified_head] if args.last_verified_head else [],
        "AUTHORIZED_FILES": args.authorized_file,
        "KNOWN_BLOCKERS": [],
        "KNOWN_UNRELATED_STATE": [],
        "ADVISOR_STATUS": "NOT_REQUIRED",
        "ADVISOR_ROUND": 0,
        "SUBAGENT_ROUND": 0,
        "NEXT_ACTION": args.next_action,
        "LAST_TEST_SUMMARY": args.test_summary,
    }
    _write_json(state_path, value, overwrite=False)
    return {"result": "success", "state_file": str(state_path), "state": value, "mutation": True}


def update_state(args: argparse.Namespace) -> dict[str, Any]:
    root = _repo_root(args.repo)
    state_path = _state_path_outside_repo(Path(args.state_file), root)
    value = _load_json(state_path)
    _valid_state(value)
    current = snapshot(root)
    _require_canonical_origin(current)
    value["CURRENT_HEAD"] = current["head"]
    if args.phase_state:
        value["PHASE_STATE"] = args.phase_state
    if args.last_verified_head:
        value["LAST_VERIFIED_HEAD"] = args.last_verified_head
        heads = value.setdefault("VERIFIED_HEADS", [])
        if args.last_verified_head not in heads:
            heads.append(args.last_verified_head)
    if args.test_summary is not None:
        value["LAST_TEST_SUMMARY"] = args.test_summary
    if args.next_action is not None:
        value["NEXT_ACTION"] = args.next_action
    _write_json(state_path, value, overwrite=True)
    return {"result": "success", "state_file": str(state_path), "state": value, "mutation": True}


def validate_envelope(repo: str | Path, envelope: dict[str, Any]) -> dict[str, Any]:
    missing = sorted(REQUIRED_ENVELOPE_KEYS - envelope.keys())
    errors: list[str] = []
    if missing:
        errors.append("missing keys: " + ", ".join(missing))
    if envelope.get("PROGRAM") != PROGRAM:
        errors.append("PROGRAM does not match the uaRO program")
    if not isinstance(envelope.get("PHASE_ID"), str) or not envelope.get("PHASE_ID"):
        errors.append("PHASE_ID must be non-empty")
    for key in ("PARENT_HEAD", "CURRENT_HEAD"):
        if not isinstance(envelope.get(key), str) or not HEAD_RE.fullmatch(envelope[key]):
            errors.append(f"{key} must be a full 40-character commit id")
    for key in (
        "AUTHORIZED_FILES",
        "AUTHORIZED_CAPABILITIES",
        "FORBIDDEN_FILES",
        "FORBIDDEN_CAPABILITIES",
        "FROZEN_INVARIANTS",
        "EXPECTED_MUTATIONS",
        "REQUIRED_EVIDENCE",
        "REQUIRED_TESTS",
    ):
        if key in envelope and not isinstance(envelope[key], list):
            errors.append(f"{key} must be a list")
    if _scopes_overlap(
        envelope.get("AUTHORIZED_FILES", []), envelope.get("FORBIDDEN_FILES", [])
    ):
        errors.append("AUTHORIZED_FILES and FORBIDDEN_FILES overlap")
    if set(envelope.get("AUTHORIZED_CAPABILITIES", [])) & set(
        envelope.get("FORBIDDEN_CAPABILITIES", [])
    ):
        errors.append("AUTHORIZED_CAPABILITIES and FORBIDDEN_CAPABILITIES overlap")
    if set(envelope.get("TERMINAL_STATES", [])) != TERMINAL_STATES:
        errors.append("TERMINAL_STATES must exactly match the five program terminal states")

    actual = snapshot(repo)
    if envelope.get("REPOSITORY") != actual["repo"]:
        errors.append("REPOSITORY does not match the repository root")
    if envelope.get("ORIGIN") != actual["origin"]:
        errors.append("ORIGIN does not match the repository origin")
    if envelope.get("ORIGIN") != CANONICAL_ORIGIN or actual["origin"] != CANONICAL_ORIGIN:
        errors.append("ORIGIN does not match the canonical uaRO repository")
    if envelope.get("BRANCH") != actual["branch"]:
        errors.append("BRANCH does not match the current branch")
    worktree_policy = envelope.get("WORKTREE_POLICY")
    if worktree_policy not in {"CLEAN_REQUIRED", "SCOPED_AUTHORIZED"}:
        errors.append("WORKTREE_POLICY must be CLEAN_REQUIRED or SCOPED_AUTHORIZED")
    elif worktree_policy == "CLEAN_REQUIRED" and actual["dirty_paths"]:
        errors.append("worktree is dirty but WORKTREE_POLICY requires CLEAN_REQUIRED")
    elif worktree_policy == "SCOPED_AUTHORIZED" and not all(
        _path_allowed(path, envelope.get("AUTHORIZED_FILES", []))
        for path in actual["dirty_paths"]
    ):
        errors.append("dirty paths exceed AUTHORIZED_FILES")
    if (
        isinstance(envelope.get("PARENT_HEAD"), str)
        and HEAD_RE.fullmatch(envelope["PARENT_HEAD"])
        and isinstance(envelope.get("CURRENT_HEAD"), str)
        and HEAD_RE.fullmatch(envelope["CURRENT_HEAD"])
    ):
        try:
            if not _is_ancestor(root := _repo_root(repo), envelope["PARENT_HEAD"], actual["head"]):
                errors.append("PARENT_HEAD is not an ancestor of the current repository HEAD")
        except ControlPlaneError:
            errors.append("PARENT_HEAD is not a reachable commit in this repository")
    if envelope.get("CURRENT_HEAD") != actual["head"]:
        errors.append("CURRENT_HEAD does not match the repository HEAD")

    return {
        "result": "success" if not errors else "blocked",
        "valid": not errors,
        "errors": errors,
        "snapshot": actual,
        "mutation": False,
        "authority": "evidence-only",
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Evidence-only uaRO engineering control plane")
    sub = parser.add_subparsers(dest="command", required=True)

    snap = sub.add_parser("snapshot", help="capture read-only repository state")
    snap.add_argument("--repo", default=".")

    rec = sub.add_parser("reconcile", help="classify repository state against a state cache")
    rec.add_argument("--repo", default=".")
    rec.add_argument("--state-file", required=True)

    env = sub.add_parser("envelope", help="validate a bounded Phase Envelope")
    env_sub = env.add_subparsers(dest="envelope_command", required=True)
    env_validate = env_sub.add_parser("validate")
    env_validate.add_argument("--repo", default=".")
    env_validate.add_argument("--file", required=True)

    state = sub.add_parser("state", help="create or update a volatile state cache")
    state_sub = state.add_subparsers(dest="state_command", required=True)
    init = state_sub.add_parser("init")
    init.add_argument("--repo", default=".")
    init.add_argument("--state-file", required=True)
    init.add_argument("--program-goal", required=True)
    init.add_argument("--phase", required=True)
    init.add_argument("--phase-state", default="INSPECTING")
    init.add_argument("--expected-parent")
    init.add_argument("--last-verified-head")
    init.add_argument("--authorized-file", action="append", default=[])
    init.add_argument("--test-summary", default="")
    init.add_argument("--next-action", required=True)
    update = state_sub.add_parser("update")
    update.add_argument("--repo", default=".")
    update.add_argument("--state-file", required=True)
    update.add_argument("--phase-state")
    update.add_argument("--last-verified-head")
    update.add_argument("--test-summary")
    update.add_argument("--next-action")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "snapshot":
            result = snapshot(args.repo)
        elif args.command == "reconcile":
            result = reconcile(args.repo, _load_json(args.state_file))
        elif args.command == "envelope":
            result = validate_envelope(args.repo, _load_json(args.file))
        elif args.command == "state" and args.state_command == "init":
            result = init_state(args)
        elif args.command == "state" and args.state_command == "update":
            result = update_state(args)
        else:
            raise ControlPlaneError("unsupported control-plane command")
    except (ControlPlaneError, OSError, TypeError, ValueError) as exc:
        print(json.dumps({"result": "blocked", "error": str(exc), "mutation": False}, sort_keys=True))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result.get("result") == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
