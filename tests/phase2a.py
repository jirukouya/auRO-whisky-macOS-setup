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
import os
from pathlib import Path
import re
import shutil
import subprocess
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
    end = section.index("### Existing FCOM mutation route", start)
    return fenced_after(section[start:end], "bash")


def legacy_fcom_mutation_block() -> str:
    section = step8_section()
    start = section.index("### Existing FCOM mutation route")
    end = section.index("### Explicit structural target inspection", start)
    return fenced_after(section[start:end], "bash")


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
        script = readonly_shell(fcom_route_block()) + "\n" + legacy_fcom_mutation_block()
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


def test_fcom_states() -> None:
    route = fcom_route_block()
    legacy = legacy_fcom_mutation_block()
    require('python3 "$AURO_EXECUTOR" fcom check "$SETUP"' in route, "FCOM route does not invoke the deterministic executor")
    require("resolve_uaro_executor" in route, "FCOM route does not resolve the executor")
    require("remote.origin.url" in shared_readonly_block(), "executor resolver does not validate repository identity")
    require("validate_uaro_json" in route, "FCOM route does not validate structured evidence")
    require("fcom apply" not in route, "FCOM mutation command was integrated into the read-only route")
    for duplicate in ("shutil.copy2", "setup.write_bytes", "def read_site", "expected_offsets", "SITE_A_OFFSET"):
        require(duplicate not in route, f"duplicate executable FCOM classifier remains in read-only route: {duplicate}")
    for required in ("shutil.copy2", "setup.write_bytes", "def read_site", "expected_offsets", "SITE_A_OFFSET"):
        require(required in legacy, f"existing Step 8 mutation route is missing: {required}")
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


def test_fcom_legacy_mutation_route() -> None:
    section = step8_section()
    legacy = legacy_fcom_mutation_block()
    require("temporary pre-Stage-2 path" in section, "temporary production mutation route is not documented")
    require("Do not substitute the later Settings launcher" in section, "Step 11 was not distinguished from Step 8 mutation")

    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    proc, final, backup = run_fcom_pipeline(original, cwd=Path(tempfile.gettempdir()))
    require(proc.returncode == 0, f"read-only check plus existing mutation route failed: {report_process(proc)}")
    require("mutation authority remains denied" in proc.stdout, "read-only check output did not remain evidence-only")
    require("FCOM patch applied and verified" in proc.stdout, "existing Step 8 mutation route did not run")
    require(final[A_OFFSET:A_OFFSET + 1] == A_PATCHED, "existing Step 8 mutation did not patch Site A")
    require(final[B_OFFSET:B_OFFSET + 4] == B_PATCHED, "existing Step 8 mutation did not patch Site B")
    require(backup == original, "existing Step 8 mutation did not preserve the original backup")


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
    cp_hook: bool = False,
    cp_failure_after_successful_copy: bool = False,
) -> subprocess.CompletedProcess:
    env = {
        "GAME_DIR": str(game),
        "HOME": str(game.parent / "home"),
        "BACKUP_ROOT": str(game.parent / "backup-root"),
        "BACKUP_DIR": str(backup_dir),
    }
    Path(env["HOME"]).mkdir(exist_ok=True)
    if cp_hook or cp_failure_after_successful_copy:
        bin_dir = game.parent / "cp-hook-bin"
        bin_dir.mkdir(exist_ok=True)
        cp = bin_dir / "cp"
        if cp_failure_after_successful_copy:
            cp.write_text("#!/bin/sh\n/bin/cp \"$@\"\nexit 1\n")
        else:
            cp.write_text(
                "#!/bin/sh\n"
                "/bin/cp \"$@\"\n"
                "last=\"\"\n"
                "for arg in \"$@\"; do last=\"$arg\"; done\n"
                "touch \"$last/mismatch-from-copy-hook\"\n"
            )
        cp.chmod(0o755)
        env["PATH"] = str(bin_dir) + os.pathsep + os.environ.get("PATH", "")
    return run_zsh(savedata_block(), env)


def test_savedata_gate() -> None:
    block = savedata_block()
    require(block.index("GAME_DIR_REAL") < block.index("mkdir -p"), "savedata path policy is checked after backup-root creation")
    require("if ! cp -R \"$SOURCE\" \"$BACKUP_DIR/savedata\"; then" in block, "savedata copy exit status is not checked")
    require(block.index("if ! cp -R") < block.index("diff -qr"), "savedata comparison can override a failed copy")
    require(block.index("diff -qr") < block.index("SAVEDATA_BACKUP_VERIFIED=1"), "deletion authority is granted before independent comparison")
    require("Savedata exists but is empty" in block, "empty savedata is not distinguished from missing savedata")
    require("Backup destination is inside GAME_DIR" in block, "backup destination boundary is missing")

    text = skill_text()
    level1_marker = "```bash\n# --- Level 1: game only ---\n"
    level1_start = text.index(level1_marker) + len("```bash\n")
    level1_end = text.index("```", level1_start)
    level1 = text[level1_start:level1_end]
    require(level1.index("SAVEDATA_BACKUP_VERIFIED") < level1.index("LSREGISTER"), "destructive uninstall lacks a final backup-verification gate")

    with tempfile.TemporaryDirectory(prefix="phase2a-savedata-") as temp:
        root = Path(temp)
        game = root / "game"
        source = game / "savedata"
        source.mkdir(parents=True)
        (source / "slot.dat").write_bytes(b"save")
        external = root / "external-backup"
        before = tree_bytes(game)
        proc = run_savedata(game, external)
        require(proc.returncode == 0, f"valid external backup failed: {report_process(proc)}")
        require((external / "savedata" / "slot.dat").read_bytes() == b"save", "external backup content is wrong")
        require(tree_bytes(game) == before, "valid backup mutated the game source")

        game_empty = root / "empty-game"
        (game_empty / "savedata").mkdir(parents=True)
        empty_backup = root / "empty-backup"
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
        (existing_source / "slot.dat").write_bytes(b"save")
        existing_backup = root / "existing-backup"
        existing_backup.mkdir()
        (existing_backup / "old").write_bytes(b"keep")
        proc = run_savedata(existing_game, existing_backup)
        require(proc.returncode != 0, "existing destination was merged instead of rejected")
        require((existing_backup / "old").read_bytes() == b"keep", "existing destination was modified")

        mismatch_game = root / "mismatch-game"
        mismatch_source = mismatch_game / "savedata"
        mismatch_source.mkdir(parents=True)
        (mismatch_source / "slot.dat").write_bytes(b"save")
        mismatch_backup = root / "mismatch-backup"
        proc = run_savedata(mismatch_game, mismatch_backup, cp_hook=True)
        require(proc.returncode != 0, f"mismatched copy unexpectedly passed: {report_process(proc)}")

        failed_copy_game = root / "failed-copy-game"
        failed_copy_source = failed_copy_game / "savedata"
        failed_copy_source.mkdir(parents=True)
        (failed_copy_source / "slot.dat").write_bytes(b"save")
        failed_copy_backup = root / "failed-copy-backup"
        proc = run_savedata(
            failed_copy_game,
            failed_copy_backup,
            cp_failure_after_successful_copy=True,
        )
        require(proc.returncode != 0, f"failed copy unexpectedly passed: {report_process(proc)}")
        require(
            "Savedata backup independently verified" not in proc.stdout,
            "failed copy was reported as verified and deletion authority was granted",
        )

        inside_source_game = root / "inside-source-game"
        (inside_source_game / "savedata").mkdir(parents=True)
        inside_source_backup = inside_source_game / "savedata" / "backup"
        proc = run_savedata(inside_source_game, inside_source_backup)
        require(proc.returncode != 0, "destination inside SOURCE was accepted")

        inside_game = root / "inside-game"
        (inside_game / "savedata").mkdir(parents=True)
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
    allowed = {"SKILL.md", "tests/phase2a.py", "tests/test_uaro.py"}
    proc = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    paths = set()
    for line in proc.stdout.splitlines():
        value = line[3:]
        if " -> " in value:
            value = value.split(" -> ", 1)[1]
        value = value.strip('"')
        if "/__pycache__/" in f"/{value}" or value.endswith(".pyc"):
            continue
        paths.add(value)
    require(paths <= allowed, f"unexpected changed paths: {sorted(paths)}")


def run_all() -> int:
    tests = (
        ("F-01 verify-only boundary", test_verify_only_boundary),
        ("F-02 read-only executor routing", test_fcom_states),
        ("F-02 existing mutation route", test_fcom_legacy_mutation_route),
        ("Stage 1 executor integrity", test_readonly_executor_integrity),
        ("F-03 execution gate", test_execution_gate),
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
