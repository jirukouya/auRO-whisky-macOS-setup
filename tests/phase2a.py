#!/usr/bin/env python3
"""Portable Phase 2A regression harness.

The read-only FCOM and structural-inspection cases route through the
production deterministic executor invoked by the procedures extracted from
SKILL.md. The savedata case still exercises the documented shell transaction;
the uaro-cli cases execute the embedded repair function with temporary app
bundles and command stubs. No real Whisky, Wine, uaRO, /Applications, or
deletion command is used.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from typing import Dict, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "SKILL.md"
EXPECTED_ORIGIN = "https://github.com/jirukouya/auRO-whisky-macOS-setup.git"
A_OFFSET = 0x2C0CD
B_OFFSET = 0x21E39
A_UNPATCHED = bytes.fromhex("dc")
A_PATCHED = bytes.fromhex("d8")
B_UNPATCHED = bytes.fromhex("dcd8dfe0")
B_PATCHED = bytes.fromhex("ddd8b440")


class SkipCase(Exception):
    pass


def fail(message: str) -> None:
    raise AssertionError(message)


def require(condition: bool, message: str) -> None:
    if not condition:
        fail(message)


def skill_text() -> str:
    return SKILL.read_text()


def fenced_after(text: str, language: str) -> str:
    fence = chr(96) * 3
    marker = fence + language
    start_marker = text.index(marker)
    start = text.index("\n", start_marker) + 1
    end = text.index(fence, start)
    return text[start:end]


def step8_section() -> str:
    text = skill_text()
    start = text.index("## Step 8 — Patch setup.exe")
    end = text.index("## Phase C — Client readiness", start)
    return text[start:end]


def shared_readonly_block() -> str:
    section = step8_section()
    start = section.index("### Shared deterministic read-only executor routing")
    end = section.index("### Read-only FCOM classification", start)
    return fenced_after(section[start:end], "bash")


def fcom_route_block() -> str:
    section = step8_section()
    start = section.index("### Read-only FCOM classification")
    end = section.index("### Deterministic FCOM mutation", start)
    return fenced_after(section[start:end], "bash")


def fcom_apply_route_block() -> str:
    section = step8_section()
    start = section.index("### Deterministic FCOM mutation")
    end = section.index("### Explicit structural target inspection", start)
    return fenced_after(section[start:end], "bash")


def step11_section() -> str:
    text = skill_text()
    start = text.index("## Step 11 — Build the three launcher .app bundles")
    end = text.index("## Optional: uaro-cli command-line helper", start)
    return text[start:end]


def inspect_route_block() -> str:
    section = step8_section()
    start = section.index("### Explicit structural target inspection")
    return fenced_after(section[start:], "bash")


def readonly_shell(route: str) -> str:
    return shared_readonly_block() + "\n" + route


def savedata_block() -> str:
    text = skill_text()
    start = text.index("The source policy distinguishes a missing path")
    return fenced_after(text[start:], "bash")


def uaro_script() -> str:
    text = skill_text()
    marker = "cat > /opt/homebrew/bin/uaro-cli <<'SCRIPT'\n"
    start = text.index(marker) + len(marker)
    end = text.index("\nSCRIPT\n", start)
    return text[start:end]


def run_zsh(
    script: str,
    env: dict[str, str],
    cwd: Optional[Path] = ROOT,
) -> subprocess.CompletedProcess[str]:
    zsh = shutil.which("zsh")
    if not zsh:
        raise SkipCase("zsh is unavailable; macOS shell procedure checks skipped")
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [zsh, "-c", script],
        cwd=cwd,
        env=merged,
        text=True,
        capture_output=True,
    )


def report_process(proc: subprocess.CompletedProcess[str]) -> str:
    output = (proc.stdout + proc.stderr).strip()
    return f"exit={proc.returncode}; output={output[:1200]}"


def fixture_binary(a_state: bytes, b_state: bytes, size: Optional[int] = None) -> bytes:
    required = max(A_OFFSET + len(A_UNPATCHED), B_OFFSET + len(B_UNPATCHED))
    size = max(size or required + 32, required)
    data = bytearray((index * 17) % 251 for index in range(size))
    data[A_OFFSET:A_OFFSET + 1] = a_state
    data[B_OFFSET:B_OFFSET + 4] = b_state
    return bytes(data)


def run_fcom_check(
    data: bytes,
    backup: Optional[bytes] = None,
    repo_root: Path = ROOT,
    cwd: Optional[Path] = None,
) -> Tuple[subprocess.CompletedProcess[str], bytes, Optional[bytes]]:
    with tempfile.TemporaryDirectory(prefix="phase2a-fcom-check-") as temp:
        root = Path(temp)
        game = root / "game dir with spaces"
        game.mkdir()
        setup = game / "setup.exe"
        backup_path = game / "setup.exe.orig-backup"
        setup.write_bytes(data)
        if backup is not None:
            backup_path.write_bytes(backup)
        proc = run_zsh(
            readonly_shell(fcom_route_block()),
            {
                "GAME_DIR": str(game),
                "AURO_REPO_ROOT": str(repo_root),
            },
            cwd=cwd or root,
        )
        final = setup.read_bytes()
        saved_backup = backup_path.read_bytes() if backup_path.exists() else None
        return proc, final, saved_backup


def run_fcom_pipeline(
    data: bytes,
    backup: Optional[bytes] = None,
    repo_root: Path = ROOT,
    cwd: Optional[Path] = None,
) -> Tuple[subprocess.CompletedProcess[str], bytes, Optional[bytes]]:
    with tempfile.TemporaryDirectory(prefix="phase2a-fcom-pipeline-") as temp:
        root = Path(temp)
        game = root / "game dir with spaces"
        game.mkdir()
        setup = game / "setup.exe"
        backup_path = game / "setup.exe.orig-backup"
        setup.write_bytes(data)
        if backup is not None:
            backup_path.write_bytes(backup)
        script = readonly_shell(fcom_route_block()) + "\n" + fcom_apply_route_block()
        proc = run_zsh(
            script,
            {
                "GAME_DIR": str(game),
                "AURO_REPO_ROOT": str(repo_root),
            },
            cwd=cwd or root,
        )
        final = setup.read_bytes()
        saved_backup = backup_path.read_bytes() if backup_path.exists() else None
        return proc, final, saved_backup


def make_fake_repo(
    root: Path,
    executor: Optional[str],
    origin: str = EXPECTED_ORIGIN,
) -> Path:
    subprocess.run(["git", "init", "-q", str(root)], check=True, capture_output=True, text=True)
    subprocess.run(["git", "-C", str(root), "remote", "add", "origin", origin], check=True, capture_output=True, text=True)
    if executor is not None:
        scripts = root / "scripts"
        scripts.mkdir()
        path = scripts / "uaro.py"
        path.write_text(executor)
        path.chmod(0o755)
    return root


def run_fake_fcom_executor(
    executor: str,
    data: bytes,
    origin: str = EXPECTED_ORIGIN,
) -> subprocess.CompletedProcess[str]:
    with tempfile.TemporaryDirectory(prefix="phase2a-fcom-fake-") as temp:
        root = Path(temp)
        fake_repo = make_fake_repo(root / "fake-repo", executor, origin=origin)
        game = root / "target"
        game.mkdir()
        (game / "setup.exe").write_bytes(data)
        return run_zsh(
            readonly_shell(fcom_route_block()),
            {
                "GAME_DIR": str(game),
                "AURO_REPO_ROOT": str(fake_repo),
            },
            cwd=root,
        )


FAKE_FCOM_EXECUTOR = r'''#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

operation = sys.argv[2]
target = sys.argv[3]
name = operation.upper()
count_path = Path(__file__).with_name(f".{operation}-count")
count = int(count_path.read_text()) if count_path.exists() else 0
count_path.write_text(str(count + 1))

raw_sequence = json.loads(os.environ.get(f"FAKE_{name}_RAW_SEQUENCE", "[]"))
if count < len(raw_sequence) and raw_sequence[count] is not None:
    print(raw_sequence[count])
else:
    payload = json.loads(os.environ[f"FAKE_{name}_JSON"])
    if operation == "check":
        states = json.loads(os.environ.get("FAKE_CHECK_STATES", "[]"))
        if count < len(states):
            payload["state"] = states[count]
            payload["site_a"] = "patched" if states[count] == "PATCHED" else "unpatched"
            payload["site_b"] = "patched" if states[count] == "PATCHED" else "unpatched"
    target_modes = json.loads(os.environ.get(f"FAKE_{name}_TARGETS", "[]"))
    target_mode = target_modes[count] if count < len(target_modes) else os.environ.get(f"FAKE_{name}_TARGET", "actual")
    if target_mode == "wrong":
        payload["target"] = target + ".wrong"
    elif "target" in payload:
        payload["target"] = target
    print(json.dumps(payload, sort_keys=True))

exit_values = json.loads(os.environ.get(f"FAKE_{name}_EXITS", "[]"))
if count < len(exit_values):
    raise SystemExit(exit_values[count])
raise SystemExit(int(os.environ.get(f"FAKE_{name}_EXIT", "0")))
'''


def run_fake_fcom_pipeline(
    executor: str,
    data: bytes,
    check_payload: Dict[str, object],
    apply_payload: Dict[str, object],
    origin: str = EXPECTED_ORIGIN,
    extra_env: Optional[Dict[str, str]] = None,
) -> Tuple[subprocess.CompletedProcess[str], bytes, Optional[bytes], int, int]:
    with tempfile.TemporaryDirectory(prefix="phase2a-fcom-pipeline-fake-") as temp:
        root = Path(temp)
        fake_repo = make_fake_repo(root / "fake-repo", executor, origin=origin)
        game = root / "game dir with spaces"
        game.mkdir()
        setup = game / "setup.exe"
        backup_path = game / "setup.exe.orig-backup"
        setup.write_bytes(data)
        env = {
            "GAME_DIR": str(game),
            "AURO_REPO_ROOT": str(fake_repo),
            "FAKE_CHECK_JSON": json.dumps(check_payload),
            "FAKE_APPLY_JSON": json.dumps(apply_payload),
        }
        if extra_env:
            env.update(extra_env)
        script = readonly_shell(fcom_route_block()) + "\n" + fcom_apply_route_block()
        proc = run_zsh(script, env, cwd=root)
        apply_count_path = fake_repo / "scripts" / ".apply-count"
        check_count_path = fake_repo / "scripts" / ".check-count"
        apply_count = int(apply_count_path.read_text()) if apply_count_path.exists() else 0
        check_count = int(check_count_path.read_text()) if check_count_path.exists() else 0
        final = setup.read_bytes()
        saved_backup = backup_path.read_bytes() if backup_path.exists() else None
        return proc, final, saved_backup, apply_count, check_count


def valid_fake_check(state: str = "UNPATCHED") -> Dict[str, object]:
    site_a = "patched" if state == "PATCHED" else "unpatched"
    site_b = "patched" if state == "PATCHED" else "unpatched"
    return {
        "operation": "fcom-check",
        "capability": "READ",
        "target": "placeholder",
        "site_a": site_a,
        "site_b": site_b,
        "state": state,
        "pre_state": state,
        "post_state": state,
        "backup_created": False,
        "mutation": False,
        "verification": "not-run",
        "result": "success",
        "reason": "classified",
    }


def valid_fake_apply(pre_state: str = "UNPATCHED", post_state: str = "PATCHED") -> Dict[str, object]:
    return {
        "operation": "fcom-apply",
        "capability": "REVERSIBLE_MUTATION",
        "target": "placeholder",
        "site_a": "patched",
        "site_b": "patched",
        "state": pre_state,
        "pre_state": pre_state,
        "post_state": post_state,
        "backup_created": pre_state == "UNPATCHED",
        "mutation": pre_state == "UNPATCHED",
        "verification": "passed",
        "result": "success",
        "reason": "patched and verified" if pre_state == "UNPATCHED" else "already patched; no-op",
    }


def test_fcom_states() -> None:
    route = fcom_route_block()
    require('python3 "$AURO_EXECUTOR" fcom check "$SETUP"' in route, "FCOM route does not invoke the deterministic executor")
    require("resolve_uaro_executor" in route, "FCOM route does not resolve the executor")
    require("remote.origin.url" in shared_readonly_block(), "executor resolver does not validate repository identity")
    require("validate_uaro_json" in route, "FCOM route does not validate structured evidence")
    require("fcom apply" not in route, "FCOM mutation command was integrated into the read-only route")
    for duplicate in ("shutil.copy2", "setup.write_bytes", "def read_site", "expected_offsets", "SITE_A_OFFSET"):
        require(duplicate not in route, f"duplicate executable FCOM classifier remains in read-only route: {duplicate}")
    require("UNPATCHED" in route and "mutation authority remains denied" in route, "UNPATCHED evidence boundary is missing")
    require("MIXED|UNKNOWN|TRUNCATED" in route, "FCOM fail-closed state handling is missing")

    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    proc, final, backup = run_fcom_check(original, cwd=Path(tempfile.gettempdir()))
    require(proc.returncode == 0, f"valid unpatched FCOM check failed: {report_process(proc)}")
    require(final == original, "read-only unpatched FCOM check modified the target")
    require(backup is None, "read-only unpatched FCOM check created a backup")
    require("mutation authority remains denied" in proc.stdout, "UNPATCHED was treated as mutation authority")

    patched = fixture_binary(A_PATCHED, B_PATCHED)
    proc, final, backup = run_fcom_check(patched, cwd=Path(tempfile.gettempdir()))
    require(proc.returncode == 0, f"already-patched FCOM check failed: {report_process(proc)}")
    require(final == patched, "already-patched read-only check modified the target")
    require(backup is None, "already-patched read-only check created a backup")

    cases = {
        "Site A unknown": fixture_binary(b"\x00", B_UNPATCHED),
        "Site B unknown": fixture_binary(A_UNPATCHED, b"\x00\x00\x00\x00"),
        "mixed state": fixture_binary(A_PATCHED, B_UNPATCHED),
        "truncated target": b"\x00" * (B_OFFSET + 2),
    }
    for name, data in cases.items():
        proc, final, backup = run_fcom_check(data, cwd=Path(tempfile.gettempdir()))
        require(proc.returncode != 0, f"{name} unexpectedly passed: {report_process(proc)}")
        require(final == data, f"{name} modified target bytes")
        require(backup is None, f"{name} created a backup despite fail-closed read-only handling")

    preserved = bytearray(original)
    preserved[-1] ^= 0xFF
    proc, final, saved_backup = run_fcom_check(original, bytes(preserved), cwd=Path(tempfile.gettempdir()))
    require(proc.returncode == 0, f"existing-backup read-only case failed: {report_process(proc)}")
    require(final == original, "existing original backup case modified the target")
    require(saved_backup == bytes(preserved), "existing original backup was modified")


def test_fcom_deterministic_mutation_route() -> None:
    section = step8_section()
    apply_route = fcom_apply_route_block()
    require("fcom apply" in apply_route, "Step 8 does not invoke deterministic fcom apply")
    require("independent post-apply FCOM check" in apply_route, "Step 8 does not require an independent post-apply check")
    require("inline shell patch" in section, "Step 8 does not prohibit a legacy mutation fallback")
    require("shutil.copy2" not in apply_route and "setup.write_bytes" not in apply_route, "active Step 8 route still contains legacy byte mutation logic")

    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    proc, final, backup = run_fcom_pipeline(original, cwd=Path(tempfile.gettempdir()))
    require(proc.returncode == 0, f"read-only check plus existing mutation route failed: {report_process(proc)}")
    require("mutation authority remains denied" in proc.stdout, "read-only check output did not remain evidence-only")
    require("FCOM apply succeeded and independent PATCHED check passed" in proc.stdout, "deterministic Step 8 mutation route did not complete")
    require(final[A_OFFSET:A_OFFSET + 1] == A_PATCHED, "deterministic Step 8 mutation did not patch Site A")
    require(final[B_OFFSET:B_OFFSET + 4] == B_PATCHED, "deterministic Step 8 mutation did not patch Site B")
    require(backup == original, "deterministic Step 8 mutation did not preserve the original backup")


def test_fcom_cutover_contract() -> None:
    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    patched = fixture_binary(A_PATCHED, B_PATCHED)

    def run_case(
        check_state: str = "UNPATCHED",
        apply_payload: Optional[Dict[str, object]] = None,
        check_states: Optional[list[str]] = None,
        extra_env: Optional[Dict[str, str]] = None,
        data: bytes = original,
    ) -> Tuple[subprocess.CompletedProcess[str], bytes, Optional[bytes], int, int]:
        return run_fake_fcom_pipeline(
            FAKE_FCOM_EXECUTOR,
            data,
            valid_fake_check(check_state),
            apply_payload or valid_fake_apply(),
            extra_env={
                **({"FAKE_CHECK_STATES": json.dumps(check_states)} if check_states is not None else {}),
                **(extra_env or {}),
            },
        )

    proc, final, backup, apply_count, check_count = run_case(
        check_state="PATCHED",
        apply_payload=valid_fake_apply(),
        extra_env={"FAKE_APPLY_EXIT": "17"},
        data=patched,
    )
    require(proc.returncode == 0, f"PATCHED initial state did not no-op: {report_process(proc)}")
    require(apply_count == 0, "PATCHED initial state invoked fcom apply")
    require(check_count == 1, "PATCHED initial state did not perform exactly one check")
    require(final == patched and backup is None, "PATCHED no-op changed target or created backup")

    proc, final, backup, apply_count, check_count = run_case(
        check_states=["UNPATCHED", "PATCHED"],
    )
    require(proc.returncode == 0, f"authorized UNPATCHED route failed: {report_process(proc)}")
    require(apply_count == 1 and check_count == 2, "authorized route did not run apply plus independent post-check")
    require(backup is None and final == original, "fake evidence route performed an unexpected fixture mutation")

    no_op_apply = valid_fake_apply(pre_state="PATCHED", post_state="PATCHED")
    proc, _, _, apply_count, check_count = run_case(
        apply_payload=no_op_apply,
        check_states=["UNPATCHED", "PATCHED"],
    )
    require(proc.returncode == 0 and apply_count == 1 and check_count == 2, "valid executor no-op after an external state change did not require independent PATCHED confirmation")

    apply_disagreement = valid_fake_apply()
    apply_disagreement["result"] = "success"
    proc, _, _, apply_count, check_count = run_case(
        apply_payload=apply_disagreement,
        extra_env={"FAKE_APPLY_EXITS": json.dumps([7])},
    )
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "JSON success with nonzero apply exit was accepted")

    for state in ("UNKNOWN", "MIXED", "TRUNCATED"):
        proc, _, _, apply_count, check_count = run_case(
            check_state=state,
            extra_env={"FAKE_APPLY_EXIT": "17"},
        )
        require(proc.returncode != 0, f"{state} initial state unexpectedly passed")
        require(apply_count == 0 and check_count == 1, f"{state} invoked apply or repeated the initial check")

    proc, _, _, apply_count, check_count = run_case(extra_env={"FAKE_CHECK_EXIT": "7"})
    require(proc.returncode != 0 and apply_count == 0 and check_count == 1, "initial check nonzero was not fail-closed")

    proc, _, _, apply_count, check_count = run_case(extra_env={"FAKE_CHECK_TARGET": "wrong"})
    require(proc.returncode != 0 and apply_count == 0 and check_count == 1, "initial check wrong target was accepted")

    proc, _, _, apply_count, check_count = run_case(
        extra_env={"FAKE_CHECK_RAW_SEQUENCE": json.dumps(["not-json"])}
    )
    require(proc.returncode != 0 and apply_count == 0 and check_count == 1, "initial malformed JSON was not fail-closed")

    proc, _, _, apply_count, check_count = run_case(extra_env={"FAKE_APPLY_EXIT": "7"})
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "apply nonzero was not fail-closed")

    proc, _, _, apply_count, check_count = run_case(
        extra_env={"FAKE_APPLY_RAW_SEQUENCE": json.dumps(["not-json"])}
    )
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "apply zero exit with malformed JSON was not fail-closed")

    incomplete = {"operation": "fcom-apply", "capability": "REVERSIBLE_MUTATION", "target": "placeholder", "result": "success", "mutation": True}
    proc, _, _, apply_count, check_count = run_case(apply_payload=incomplete)
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "incomplete apply JSON was accepted")

    wrong_operation = valid_fake_apply()
    wrong_operation["operation"] = "fcom-check"
    proc, _, _, apply_count, check_count = run_case(apply_payload=wrong_operation)
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "wrong apply operation was accepted")

    proc, _, _, apply_count, check_count = run_case(extra_env={"FAKE_APPLY_TARGET": "wrong"})
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "wrong apply target was accepted")

    proc, _, _, apply_count, check_count = run_case(
        check_states=["UNPATCHED", "PATCHED"],
        extra_env={"FAKE_CHECK_TARGETS": json.dumps(["actual", "wrong"])},
    )
    require(proc.returncode != 0 and apply_count == 1 and check_count == 2, "wrong independent post-check target was accepted")

    wrong_capability = valid_fake_apply()
    wrong_capability["capability"] = "READ"
    proc, _, _, apply_count, check_count = run_case(apply_payload=wrong_capability)
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "wrong apply capability was accepted")

    nonpatched = valid_fake_apply(post_state="UNPATCHED")
    proc, _, _, apply_count, check_count = run_case(apply_payload=nonpatched)
    require(proc.returncode != 0 and apply_count == 1 and check_count == 1, "apply success with non-PATCHED final state was accepted")

    proc, _, _, apply_count, check_count = run_case(check_states=["UNPATCHED", "UNKNOWN"])
    require(proc.returncode != 0 and apply_count == 1 and check_count == 2, "non-PATCHED independent post-check was accepted")

    proc, _, _, apply_count, check_count = run_case(
        check_states=["UNPATCHED", "PATCHED"],
        extra_env={"FAKE_CHECK_RAW_SEQUENCE": json.dumps([None, "not-json"])},
    )
    require(proc.returncode != 0 and apply_count == 1 and check_count == 2, "malformed independent post-check was accepted")

    proc, _, _, apply_count, check_count = run_case(
        check_states=["UNPATCHED", "PATCHED"],
        extra_env={"FAKE_CHECK_EXITS": json.dumps([0, 7])},
    )
    require(proc.returncode != 0 and apply_count == 1 and check_count == 2, "nonzero independent post-check was accepted")

    section = step8_section()
    apply_route = fcom_apply_route_block()
    require("setup.write_bytes" not in apply_route and "shutil.copy2" not in apply_route, "legacy Step 8 mutation HOW remains active")
    require("fcom apply" in apply_route and apply_route.count("fcom check") >= 1, "deterministic apply/check route is incomplete")
    require("fcom apply" not in fcom_route_block(), "initial read-only route became self-authorizing")
    require("SAVEDATA_BACKUP_VERIFIED" not in section, "savedata routing was integrated into Step 8")
    step11 = step11_section()
    for legacy_marker in ("_patch_setup_exe", "dd if=", "xxd -p", "printf '\\xd8'", "printf '\\xdd\\xd8\\xb4\\x40'"):
        require(legacy_marker not in step11, f"retired Step 11 inline FCOM marker remains: {legacy_marker}")


def test_readonly_executor_integrity() -> None:
    section = step8_section()
    route = fcom_route_block() + "\n" + inspect_route_block()
    require("/Users/" not in section and "/home/" not in section, "private absolute path was embedded in SKILL integration")
    require("fcom apply" not in route, "FCOM apply was integrated")
    require("backup savedata" not in route, "savedata backup was integrated")
    require("EXECUTION=UNCONFIRMED" in inspect_route_block(), "inspect route does not keep execution unconfirmed")
    require("BEHAVIOR=UNCONFIRMED" in inspect_route_block(), "inspect route does not keep behavior unconfirmed")
    require("UaRO Game.app" in inspect_route_block() and 'required") is not False' in inspect_route_block(), "optional Game.app policy is missing")

    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    with tempfile.TemporaryDirectory(prefix="phase2a-inspect-") as temp:
        root = Path(temp)
        game = root / "game"
        game.mkdir()
        (game / "setup.exe").write_bytes(original)
        (game / "uaRO.exe").write_bytes(b"fixture")
        (game / "savedata").mkdir()
        apps = root / "apps"
        for name in ("UaRO Patcher.app", "UaRO Settings.app"):
            (apps / name).mkdir(parents=True)
        before = tree_bytes(root)
        proc = run_zsh(
            readonly_shell(inspect_route_block()),
            {
                "GAME_DIR": str(game),
                "APPS_DIR": str(apps),
                "AURO_REPO_ROOT": str(ROOT),
            },
            cwd=root,
        )
        require(proc.returncode == 0, f"structural inspect route failed: {report_process(proc)}")
        require("TARGET=PASS (explicit structural evidence only)" in proc.stdout, "inspect route did not report structural target evidence")
        require("EXECUTION=UNCONFIRMED; BEHAVIOR=UNCONFIRMED" in proc.stdout, "inspect route claimed runtime or behavior proof")
        require(tree_bytes(root) == before, "structural inspect route mutated its target fixture")

        missing = root / "missing-game"
        missing.mkdir()
        proc = run_zsh(
            readonly_shell(inspect_route_block()),
            {
                "GAME_DIR": str(missing),
                "APPS_DIR": str(apps),
                "AURO_REPO_ROOT": str(ROOT),
            },
            cwd=root,
        )
        require(proc.returncode != 0, "inspect route passed with a missing target")

    missing_proc = run_fake_fcom_executor("#!/bin/sh\nexit 0\n", original)
    require(missing_proc.returncode != 0, "missing executor unexpectedly passed")

    malformed = "#!/bin/sh\nprintf 'not-json\\n'\n"
    malformed_proc = run_fake_fcom_executor(malformed, original)
    require(malformed_proc.returncode != 0, "malformed executor JSON unexpectedly passed")

    incomplete = "#!/bin/sh\nprintf '{\"operation\":\"fcom-check\",\"result\":\"success\",\"mutation\":false}\\n'\n"
    incomplete_proc = run_fake_fcom_executor(incomplete, original)
    require(incomplete_proc.returncode != 0, "incomplete executor JSON unexpectedly passed")

    nonzero = "#!/bin/sh\nprintf '{\"operation\":\"fcom-check\"}\\n'\nexit 7\n"
    nonzero_proc = run_fake_fcom_executor(nonzero, original)
    require(nonzero_proc.returncode != 0, "nonzero executor exit unexpectedly passed")

    wrong_origin_proc = run_fake_fcom_executor(
        "#!/bin/sh\nexit 0\n",
        original,
        origin="https://example.invalid/wrong-repository.git",
    )
    require(wrong_origin_proc.returncode != 0, "wrong repository origin unexpectedly supplied an executor")

def tree_bytes(path: Path) -> Dict[str, bytes]:
    return {
        str(item.relative_to(path)): item.read_bytes()
        for item in path.rglob("*")
        if item.is_file()
    }


def run_savedata(
    game: Path,
    backup_dir: Path,
    repo_root: Path = ROOT,
) -> subprocess.CompletedProcess:
    env = {
        "GAME_DIR": str(game),
        "HOME": str(game.parent / "home"),
        "BACKUP_ROOT": str(game.parent / "backup-root"),
        "BACKUP_DIR": str(backup_dir),
        "UNINSTALL_LEVEL": "1",
        "AURO_REPO_ROOT": str(repo_root),
        "PYTHON_RUNTIME": sys.executable,
    }
    Path(env["HOME"]).mkdir(exist_ok=True)
    return run_zsh(savedata_block(), env)


def test_savedata_gate() -> None:
    block = savedata_block()
    require("backup savedata" in block, "savedata route does not invoke the deterministic executor")
    require("BACKUP_JSON" in block and "backup_verified" in block, "savedata route does not validate structured evidence")
    require("comparison.get(\"status\") != \"equal\"" in block, "savedata route does not require independent comparison")
    require(block.index("BACKUP_EVIDENCE_VERIFIED=1") > block.index("backup_verified"), "backup evidence is emitted before executor validation")
    require("UNINSTALL_LEVEL=\"${UNINSTALL_LEVEL:?" in block, "uninstall level is not explicitly selected for this invocation")
    require("cp -R" not in block and "diff -qr" not in block, "legacy shell savedata transaction remains active")

    text = skill_text()
    level1_marker = "```bash\n[[ \"${UNINSTALL_LEVEL:-}\" == 1 ]]"
    level1_start = text.index(level1_marker) + len("```bash\n")
    level1_end = text.index("```", level1_start)
    level1 = text[level1_start:level1_end]
    require(level1.index("BACKUP_EVIDENCE_VERIFIED") < level1.index("LSREGISTER"), "destructive uninstall lacks a final backup-evidence gate")

    with tempfile.TemporaryDirectory(prefix="phase2a-savedata-") as temp:
        root = Path(temp) / "fixture root with spaces"
        root.mkdir()
        game = root / "game"
        source = game / "savedata"
        source.mkdir(parents=True)
        (game / "setup.exe").write_bytes(b"setup")
        (game / "uaRO.exe").write_bytes(b"uaro")
        (source / "slot.dat").write_bytes(b"save")
        external = root / "backup-root" / "external-backup"
        before = tree_bytes(game)
        proc = run_savedata(game, external)
        require(proc.returncode == 0, f"valid external backup failed: {report_process(proc)}")
        require((external / "savedata" / "slot.dat").read_bytes() == b"save", "external backup content is wrong")
        require(tree_bytes(game) == before, "valid backup mutated the game source")

        game_empty = root / "empty-game"
        (game_empty / "savedata").mkdir(parents=True)
        (game_empty / "setup.exe").write_bytes(b"setup")
        (game_empty / "uaRO.exe").write_bytes(b"uaro")
        empty_backup = root / "backup-root" / "empty-backup"
        proc = run_savedata(game_empty, empty_backup)
        require(proc.returncode == 0, f"empty existing savedata failed: {report_process(proc)}")
        require((empty_backup / "savedata").is_dir(), "empty savedata backup directory is missing")

        missing_game = root / "missing-game"
        missing_game.mkdir()
        proc = run_savedata(missing_game, root / "missing-backup")
        require(proc.returncode != 0, "missing savedata unexpectedly allowed backup")

        existing_game = root / "existing-game"
        existing_source = existing_game / "savedata"
        existing_source.mkdir(parents=True)
        (existing_game / "setup.exe").write_bytes(b"setup")
        (existing_game / "uaRO.exe").write_bytes(b"uaro")
        (existing_source / "slot.dat").write_bytes(b"save")
        existing_backup = root / "existing-backup"
        existing_backup.mkdir()
        (existing_backup / "old").write_bytes(b"keep")
        proc = run_savedata(existing_game, existing_backup)
        require(proc.returncode != 0, "existing destination was merged instead of rejected")
        require((existing_backup / "old").read_bytes() == b"keep", "existing destination was modified")

        malformed_repo = root / "malformed-repo"
        (malformed_repo / "scripts").mkdir(parents=True)
        write_executable(malformed_repo / "scripts" / "uaro.py", "#!/usr/bin/env python3\nprint('{}')\n")
        malformed_game = root / "malformed-game"
        (malformed_game / "savedata").mkdir(parents=True)
        (malformed_game / "setup.exe").write_bytes(b"setup")
        (malformed_game / "uaRO.exe").write_bytes(b"uaro")
        (malformed_game / "savedata" / "slot.dat").write_bytes(b"save")
        proc = run_savedata(malformed_game, root / "malformed-backup", repo_root=malformed_repo)
        require(proc.returncode != 0, f"malformed executor evidence unexpectedly passed: {report_process(proc)}")
        require("BACKUP_EVIDENCE_VERIFIED=1" not in proc.stdout, "malformed evidence granted deletion authority")

        failed_repo = root / "failed-repo"
        (failed_repo / "scripts").mkdir(parents=True)
        write_executable(failed_repo / "scripts" / "uaro.py", "#!/usr/bin/env python3\nraise SystemExit(7)\n")
        failed_game = root / "failed-game"
        (failed_game / "savedata").mkdir(parents=True)
        (failed_game / "setup.exe").write_bytes(b"setup")
        (failed_game / "uaRO.exe").write_bytes(b"uaro")
        (failed_game / "savedata" / "slot.dat").write_bytes(b"save")
        proc = run_savedata(failed_game, root / "failed-backup", repo_root=failed_repo)
        require(proc.returncode != 0, f"failed executor unexpectedly passed: {report_process(proc)}")

        inside_source_game = root / "inside-source-game"
        (inside_source_game / "savedata").mkdir(parents=True)
        (inside_source_game / "setup.exe").write_bytes(b"setup")
        (inside_source_game / "uaRO.exe").write_bytes(b"uaro")
        inside_source_backup = inside_source_game / "savedata" / "backup"
        proc = run_savedata(inside_source_game, inside_source_backup)
        require(proc.returncode != 0, "destination inside SOURCE was accepted")

        inside_game = root / "inside-game"
        (inside_game / "savedata").mkdir(parents=True)
        (inside_game / "setup.exe").write_bytes(b"setup")
        (inside_game / "uaRO.exe").write_bytes(b"uaro")
        inside_game_backup = inside_game / "backup"
        proc = run_savedata(inside_game, inside_game_backup)
        require(proc.returncode != 0, "destination inside GAME_DIR was accepted")


def test_verify_only_boundary() -> None:
    text = skill_text()
    start = text.index("### Verify-only capability boundary (F-01)")
    end = text.index("## 1. Parameters", start)
    section = text[start:end]
    for phrase in (
        "read, inspect, query, hash, compare",
        "non-mutating process inspection",
        "write, patch, install, delete, update",
        "registry writes",
        "downloads",
        "codesign",
        "registration",
        "automatic repair",
        "mutable patcher/game launch",
        "UNCONFIRMED",
        "denylist is only a regression heuristic",
        "not complete capability enforcement",
    ):
        require(phrase in section, f"verify-only boundary missing: {phrase}")

    with tempfile.TemporaryDirectory(prefix="phase2a-verify-") as temp:
        fixture = Path(temp) / "fixture.bin"
        fixture.write_bytes(b"verify-only fixture")
        before = fixture.read_bytes()
        before_hash = hashlib.sha256(before).digest()
        _ = fixture.read_bytes()
        _ = hashlib.sha256(fixture.read_bytes()).digest()
        require(fixture.read_bytes() == before, "verify-only fixture changed")
        require(hashlib.sha256(fixture.read_bytes()).digest() == before_hash, "verify-only hash changed")


def static_execution_check(script: str, bottle: str, game_dir: str, runtime: str) -> bool:
    if any(token in script for token in ("<BOTTLE_NAME>", "<GAME_DIR>", "<RUNTIME>")):
        return False
    required = (
        f'BOTTLE_NAME="{bottle}"',
        f'GAME_DIR="{game_dir}"',
        runtime,
        "WINEPREFIX",
        "WINEDLLOVERRIDES",
    )
    return all(item in script for item in required)


def test_execution_gate() -> None:
    text = skill_text()
    start = text.index("### Execution-evidence procedure (F-03)")
    end = text.index("## Installation complete", start)
    section = text[start:end]
    for phrase in (
        "What the launcher says",
        "What actually executed",
        "bottle literal",
        "game directory",
        "unresolved placeholders",
        "Whisky CLI resolution",
        "DLL overrides",
        "shellenv",
        "WINEPREFIX",
        "runtime executable",
        "wine64 --version",
        "Do not launch a process merely",
        "EXECUTION = UNCONFIRMED",
        "Target = PASS does not imply Execution = PASS",
        "Behavior = PASS does not imply Execution = PASS",
    ):
        require(phrase in section, f"execution gate missing: {phrase}")

    valid = "\n".join(
        (
            'BOTTLE_NAME="uaro"',
            'GAME_DIR="/tmp/game"',
            'RUNTIME="/tmp/runtime/wine64"',
            'WINEPREFIX="/tmp/prefix"',
            'WINEDLLOVERRIDES="d3d9="',
        )
    )
    require(static_execution_check(valid, "uaro", "/tmp/game", "/tmp/runtime/wine64"), "valid static execution fixture failed")
    require(not static_execution_check(valid.replace('BOTTLE_NAME="uaro"', 'BOTTLE_NAME="<BOTTLE_NAME>"'), "uaro", "/tmp/game", "/tmp/runtime/wine64"), "unresolved bottle placeholder was accepted")
    require(not static_execution_check(valid.replace('RUNTIME="/tmp/runtime/wine64"', 'RUNTIME="/wrong/runtime/wine64"'), "uaro", "/tmp/game", "/tmp/runtime/wine64"), "wrong runtime fixture was accepted")
    require("EXECUTION = UNCONFIRMED" in section, "unavailable live evidence is not left UNCONFIRMED")


def settings_route_script() -> str:
    section = step11_section()
    start = section.index("### Stage 2.2B — bundle-local Settings route")
    end = section.index("### App icon", start)
    route = section[start:end]
    marker = 'cat > "/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings" <<\'EOF\'\n'
    script_start = route.index(marker) + len(marker)
    script_end = route.index("\nEOF\n", script_start)
    return route[script_start:script_end]


def run_settings_route_case(mode: str, python_failure: bool = False) -> Tuple[subprocess.CompletedProcess[str], bool, bool, str]:
    with tempfile.TemporaryDirectory(prefix="phase2b-settings-route-") as temp:
        root = Path(temp)
        fixture_root = root / "fixture root with spaces"
        fixture_root.mkdir()
        game = fixture_root / "game dir with spaces"
        game.mkdir()
        (game / "setup.exe").write_bytes(b"setup fixture")
        runtime = fixture_root / "bundle resources with spaces"
        runtime.mkdir()
        bin_dir = fixture_root / "fake bin"
        bin_dir.mkdir()
        launch_marker = fixture_root / "setup-launched"
        legacy_marker = fixture_root / "legacy-mutation-invoked"
        prefix_path = fixture_root / "wineprefix"
        prefix_path.mkdir()

        write_executable(
            runtime / "settings_runtime_verify.py",
            """#!/usr/bin/env python3
import json
import os
if os.environ.get("SETTINGS_ROUTE_MODE") == "verifier-fail":
    raise SystemExit(17)
print(json.dumps({"result": "PASS", "executor_verified": True, "verifier_verified": True, "python_verified": True}))
""",
        )
        write_executable(
            runtime / "uaro.py",
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

operation = sys.argv[2]
target = sys.argv[3]
trace = Path(__file__).with_name("executor-trace")
trace.write_text(trace.read_text() + operation + "\\n" if trace.exists() else operation + "\\n")
mode = os.environ.get("SETTINGS_ROUTE_MODE", "success")
if operation == "apply":
    if mode == "apply-fail":
        raise SystemExit(23)
    if mode == "malformed-apply":
        print("{")
        raise SystemExit(0)
    payload = {
        "operation": "fcom-apply", "capability": "REVERSIBLE_MUTATION", "result": "success",
        "mutation": True, "target": target, "state": "UNPATCHED", "pre_state": "UNPATCHED",
        "post_state": "PATCHED", "site_a": "patched", "site_b": "patched",
        "backup_created": True, "verification": "passed", "reason": "patched and verified",
    }
    print(json.dumps(payload, sort_keys=True))
    raise SystemExit(0)

check_count_path = Path(__file__).with_name("check-count")
check_count = int(check_count_path.read_text()) if check_count_path.exists() else 0
check_count_path.write_text(str(check_count + 1))
if mode == "post-check-fail" and check_count == 1:
    raise SystemExit(29)
state = "PATCHED" if check_count == 1 and mode != "post-check-not-patched" else "UNPATCHED"
payload = {
    "operation": "fcom-check", "capability": "READ", "result": "success", "mutation": False,
    "target": target, "state": state, "site_a": "patched" if state == "PATCHED" else "unpatched",
    "site_b": "patched" if state == "PATCHED" else "unpatched", "backup_created": False,
    "verification": "not-run", "reason": "classified",
}
print(json.dumps(payload, sort_keys=True))
""",
        )
        (runtime / "MANIFEST.json").write_text("{}")

        write_executable(
            bin_dir / "whisky",
            f'''#!/bin/sh
if [ "$1" = "shellenv" ]; then
  printf "export WINEPREFIX='%s'\\n" "{prefix_path}"
fi
''',
        )
        for command in ("wineserver", "pkill", "sleep"):
            write_executable(bin_dir / command, "#!/bin/sh\nexit 0\n")
        write_executable(
            bin_dir / "wine64",
            f'''#!/bin/sh
echo "$*" > "{launch_marker}"
exit 0
''',
        )
        for command in ("dd", "xxd"):
            write_executable(bin_dir / command, f'''#!/bin/sh
echo {command} >> "{legacy_marker}"
exit 99
''')

        recorded_python: Path
        if python_failure:
            recorded_python = fixture_root / "recorded python"
            recorded_python.write_text(
                "#!/bin/sh\n"
                f'if [ "$1" = "{runtime / "settings_runtime_verify.py"}" ]; then exit 31; fi\n'
                f'exec "{os.sys.executable}" "$@"\n'
            )
            recorded_python.chmod(0o755)
        else:
            recorded_python = Path(os.sys.executable)

        script = settings_route_script()
        replacements = {
            "<BOTTLE_NAME>": "bottle with spaces",
            "<GAME_DIR>": str(game),
            "<RECORDED_PYTHON>": str(recorded_python),
            "<RUNTIME_DIR>": str(runtime),
        }
        for placeholder, value in replacements.items():
            script = script.replace(placeholder, value)
        env = {
            "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
            "SETTINGS_ROUTE_MODE": mode,
        }
        proc = run_zsh(script, env, cwd=root)
        launched = launch_marker.exists()
        legacy_called = legacy_marker.exists()
        trace_path = runtime / "executor-trace"
        trace = trace_path.read_text() if trace_path.exists() else ""
        return proc, launched, legacy_called, trace


def test_stage22b_bundle_settings_route() -> None:
    section = step11_section()
    start = section.index("### Stage 2.2B — bundle-local Settings route")
    end = section.index("### App icon", start)
    route = section[start:end]
    for phrase in (
        "build_settings_runtime.py",
        "--python \"$PYTHON_RUNTIME\"",
        "settings_runtime_verify.py",
        'payload.get("result") != "PASS"',
        'fcom apply \"$SETUP\"',
        "validate_bundled_executor_json",
        "independent post-apply FCOM check",
        'payload.get(\"state\") != \"PATCHED\"',
        'exec wine64 \"setup.exe\"',
    ):
        require(phrase in route, f"Stage 2.2B route is missing: {phrase}")
    for legacy_marker in ("_patch_setup_exe", "dd if=", "xxd -p", "printf '\\xd8'", "printf '\\xdd\\xd8\\xb4\\x40'"):
        require(legacy_marker not in section, f"active Step 11 legacy mutation marker remains: {legacy_marker}")
    require("fcom check" in route and route.count("fcom check") >= 2, "Stage 2.2B route lacks independent post-check")
    require(route.count('"$RUNTIME_DIR/uaro.py" fcom apply "$SETUP")') == 1, "Stage 2.2B route has more than one active apply HOW")


def test_stage22b_route_fail_closed() -> None:
    proc, launched, legacy_called, trace = run_settings_route_case("success")
    require(proc.returncode == 0 and launched, f"valid Settings route did not launch setup.exe: {report_process(proc)}")
    require(trace.splitlines() == ["check", "apply", "check"], f"valid route did not reach apply and independent check: {trace!r}")
    require(not legacy_called, "valid route invoked a retired shell mutation command")

    proc, launched, legacy_called, trace = run_settings_route_case("verifier-fail")
    require(proc.returncode != 0 and not launched and not legacy_called, "verifier failure launched setup or invoked legacy mutation")
    require(trace == "", "verifier failure reached the bundled executor")

    proc, launched, legacy_called, trace = run_settings_route_case("success", python_failure=True)
    require(proc.returncode != 0 and not launched and not legacy_called, "Python runtime failure launched setup or invoked legacy mutation")
    require(trace == "", "Python runtime failure reached the bundled executor")

    for mode, expected_trace in (
        ("apply-fail", ["check", "apply"]),
        ("malformed-apply", ["check", "apply"]),
        ("post-check-fail", ["check", "apply", "check"]),
        ("post-check-not-patched", ["check", "apply", "check"]),
    ):
        proc, launched, legacy_called, trace = run_settings_route_case(mode)
        require(proc.returncode != 0 and not launched and not legacy_called, f"{mode} did not fail closed")
        require(trace.splitlines() == expected_trace, f"{mode} reached an unexpected route stage: {trace!r}")

    section = step11_section()
    for legacy_marker in ("_patch_setup_exe", "dd if=", "xxd -p", "printf '\\xd8'", "printf '\\xdd\\xd8\\xb4\\x40'"):
        require(legacy_marker not in section, f"legacy mutation marker remains reachable in Step 11: {legacy_marker}")
    require("fcom apply \"$SETUP\"" in settings_route_script(), "deterministic Settings route does not own mutation")


def write_executable(path: Path, content: str) -> None:
    path.write_text(content)
    path.chmod(0o755)


def make_uaro_fixture(
    root: Path,
    game: bool = True,
    bottle: bool = True,
    apps: bool = True,
    invalid_plist: bool = False,
    missing_launcher: Optional[str] = None,
) -> Tuple[Path, Dict[str, str]]:
    app_root = root / "apps"
    game_dir = root / "game"
    tool_bin = root / "bin"
    app_root.mkdir()
    game_dir.mkdir()
    tool_bin.mkdir()

    if game:
        (game_dir / "uaRO.exe").write_bytes(b"fixture")
    if apps:
        for name, executable in (
            ("UaRO Patcher.app", "uaro-patcher"),
            ("UaRO Settings.app", "uaro-settings"),
        ):
            if missing_launcher and name.startswith(f"UaRO {missing_launcher}.app"):
                continue
            bundle = app_root / name
            (bundle / "Contents" / "MacOS").mkdir(parents=True)
            write_executable(
                bundle / "Contents" / "MacOS" / executable,
                '#!/bin/zsh\nWHISKY="$(command -v whisky)"\n# command -v whisky\n',
            )
            plist = bundle / "Contents" / "Info.plist"
            plist.write_text("INVALID" if invalid_plist and name.startswith("UaRO Patcher") else "<plist><dict/></plist>")

    write_executable(
        tool_bin / "whisky",
        "#!/bin/sh\n"
        'if [ "$1" = "list" ] && [ "$WHISKY_HAS_BOTTLE" = "1" ]; then echo "$BOTTLE_NAME_FOR_TEST"; fi\n',
    )
    write_executable(
        tool_bin / "codesign",
        "#!/bin/sh\n"
        'if [ "$1" = "-dv" ]; then exit 0; fi\n'
        "exit 0\n",
    )
    write_executable(
        tool_bin / "plutil",
        "#!/bin/sh\n"
        'if [ "$1" = "-lint" ] && grep -q INVALID "$2"; then exit 1; fi\n'
        "exit 0\n",
    )
    lsregister = tool_bin / "lsregister"
    write_executable(
        lsregister,
        "#!/bin/sh\n"
        'if [ "$1" = "-dump" ]; then\n'
        '  echo "identifier: com.uaro.patcher"\n'
        '  echo "identifier: com.uaro.settings"\n'
        '  echo "identifier: com.uaro.game"\n'
        "fi\n"
        "exit 0\n",
    )
    return app_root, {
        "APP_ROOT": str(app_root),
        "GAME_DIR": str(game_dir),
        "TEST_LSREGISTER": str(lsregister),
        "BOTTLE_NAME_FOR_TEST": "uaro",
        "WHISKY_HAS_BOTTLE": "1" if bottle else "0",
        "PATH": str(tool_bin) + os.pathsep + os.environ.get("PATH", ""),
    }


def run_uaro_case(root: Path, missing_launcher: Optional[str] = None, **kwargs: bool) -> subprocess.CompletedProcess:
    app_root, env = make_uaro_fixture(root, missing_launcher=missing_launcher, **kwargs)
    script = uaro_script()
    script = script.replace('BOTTLE_NAME="<BOTTLE_NAME>"', 'BOTTLE_NAME="uaro"')
    script = script.replace('GAME_DIR="<GAME_DIR>"', f'GAME_DIR="{env["GAME_DIR"]}"')
    script = script.replace(
        'LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"',
        'LSREGISTER="$TEST_LSREGISTER"',
    )
    script = script.replace('local bundle="/Applications/$APP"', 'local bundle="$APP_ROOT/$APP"')
    cli = root / "uaro-cli"
    write_executable(cli, script)
    env["PATH"] = env["PATH"]
    env["APP_ROOT"] = str(app_root)
    return subprocess.run(
        ["zsh", str(cli), "repair"],
        cwd=ROOT,
        env={**os.environ, **env},
        text=True,
        capture_output=True,
    )


def test_uaro_cli() -> None:
    if not shutil.which("zsh"):
        raise SkipCase("zsh is unavailable; embedded zsh repair checks skipped")
    source = uaro_script()
    require("local required=0" in source, "uaro-cli required-launcher classification is missing")
    require("required launcher is missing" in source, "uaro-cli required absence is not accumulated")
    require("optional launcher not installed, skipping" in source, "optional Game.app handling is missing")
    require("if [[ $problems -eq 0 ]]" in source, "uaro-cli final problems decision is missing")
    require("if [[ $any -eq 0 ]]" not in source, "zero-launcher healthy-success path remains")
    require("pkill -f" not in source, "uaro-cli still uses an unscoped process kill")

    cases = (
        ("healthy required state with optional Game.app absent", {}, 0),
        ("missing game", {"game": False}, 1),
        ("missing bottle", {"bottle": False}, 1),
        ("missing both", {"game": False, "bottle": False}, 1),
        ("zero required launchers", {"apps": False}, 1),
        ("missing Patcher launcher", {"missing_launcher": "Patcher"}, 1),
        ("missing Settings launcher", {"missing_launcher": "Settings"}, 1),
        ("invalid required plist", {"invalid_plist": True}, 1),
    )
    for name, options, expected in cases:
        with tempfile.TemporaryDirectory(prefix="phase2a-uaro-") as temp:
            proc = run_uaro_case(Path(temp), **options)
            require(
                (proc.returncode == expected),
                f"{name} returned {proc.returncode}: {report_process(proc)}",
            )
            if name.startswith("healthy"):
                require("optional launcher not installed, skipping" in proc.stdout, "optional Game.app absence was not treated as optional")


def test_scope() -> None:
    # Phase 2C adds a bounded AzzyAI safety executor and its direct tests. Keep
    # the scope gate explicit so unrelated files still fail closed.
    # Phase 2C adds a bounded AzzyAI safety executor and its direct tests.
    # Phase 0 adds the evidence-only engineering control plane. Keep the scope
    # gate explicit so unrelated files still fail closed.
    allowed = {
        "AGENTS.md",
        "AZZYAI_FIXES.md",
        ".github/workflows/verify.yml",
        "CHANGELOG.md",
        "README.md",
        "SKILL.md",
        "TROUBLESHOOTING.md",
        "scripts/azzyai.py",
        "scripts/build_settings_runtime.py",
        "scripts/engineering_control.py",
        "scripts/settings_runtime_verify.py",
        "scripts/whisky.py",
        "scripts/whiskywine.py",
        "scripts/uaro.py",
        "tests/README.md",
        "tests/phase2a.py",
        "tests/test_azzyai.py",
        "tests/test_ci_workflow.py",
        "tests/test_engineering_control.py",
        "tests/test_settings_runtime.py",
        "tests/test_whisky.py",
        "tests/test_uaro.py",
        "tests/fixtures/azzyai-dc014477.manifest.json",
        "tests/fixtures/azzyai-synthetic.manifest.json",
    }
    allowed_fixture_prefixes = ("tests/fixtures/azzyai-synthetic/",)
    deleted_legacy_fixture_prefix = "tests/fixtures/azzyai-dc014477/"
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    paths = set()
    deleted_legacy_paths = set()
    for line in proc.stdout.splitlines():
        status = line[:2]
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        value = value.strip('"')
        if "/__pycache__/" in f"/{value}" or value.endswith(".pyc"):
            continue
        paths.add(value)
        if value.startswith(deleted_legacy_fixture_prefix) and "D" in status:
            deleted_legacy_paths.add(value)
    unexpected = {
        path
        for path in paths
        if path not in allowed
        and path not in deleted_legacy_paths
        and not any(path.startswith(prefix) for prefix in allowed_fixture_prefixes)
    }
    require(not unexpected, f"unexpected changed paths: {sorted(unexpected)}")


def run_all() -> int:
    tests = (
        ("F-01 verify-only boundary", test_verify_only_boundary),
        ("F-02 read-only executor routing", test_fcom_states),
        ("F-02 deterministic mutation route", test_fcom_deterministic_mutation_route),
        ("Stage 2.1 FCOM cutover contract", test_fcom_cutover_contract),
        ("Stage 1 executor integrity", test_readonly_executor_integrity),
        ("F-03 execution gate", test_execution_gate),
        ("Stage 2.2B bundle Settings route", test_stage22b_bundle_settings_route),
        ("Stage 2.2B fail-closed route integration", test_stage22b_route_fail_closed),
        ("F-05 uaro-cli false-success", test_uaro_cli),
        ("F-06 savedata backup gate", test_savedata_gate),
        ("scope", test_scope),
    )
    passed = []
    skipped = []
    failed = []
    for name, function in tests:
        try:
            function()
        except SkipCase as exc:
            skipped.append((name, str(exc)))
        except Exception as exc:
            failed.append((name, exc))
            print(f"FAIL {name}: {exc}")
            traceback.print_exc()
        else:
            passed.append(name)
            print(f"PASS {name}")

    print()
    print(f"SUMMARY pass={len(passed)} fail={len(failed)} skip={len(skipped)} total={len(tests)}")
    if skipped:
        for name, reason in skipped:
            print(f"SKIP {name}: {reason}")
    if failed:
        for name, exc in failed:
            print(f"FAIL {name}: {exc}")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the local Phase 2A regression harness.")
    parser.add_argument("--run", action="store_true", help="run the fixture-based checks")
    args = parser.parse_args()
    if not args.run:
        parser.print_help()
        return 0
    return run_all()


if __name__ == "__main__":
    raise SystemExit(main())
