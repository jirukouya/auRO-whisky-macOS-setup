#!/usr/bin/env python3
"""Portable Phase 2A regression harness.

The FCOM and savedata cases execute the shell/Python procedures extracted from
SKILL.md against temporary fixtures. The uaro-cli cases execute the embedded
repair function with temporary app bundles and command stubs. No real
Whisky, Wine, uaRO, /Applications, or deletion command is used.
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
A_OFFSET = 0x2C0CD
B_OFFSET = 0x21E39
A_UNPATCHED = bytes.fromhex("dc")
A_PATCHED = bytes.fromhex("d8")
B_UNPATCHED = bytes.fromhex("dcd8dfe0")
B_PATCHED = bytes.fromhex("ddd8b440")
EXPECTED_CHANGED = {A_OFFSET, B_OFFSET, B_OFFSET + 2, B_OFFSET + 3}


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


def step8_block() -> str:
    text = skill_text()
    start = text.index("## Step 8 — Patch setup.exe")
    end = text.index("## Phase C — Client readiness", start)
    return fenced_after(text[start:end], "bash")


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


def run_zsh(script: str, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    zsh = shutil.which("zsh")
    if not zsh:
        raise SkipCase("zsh is unavailable; macOS shell procedure checks skipped")
    merged = os.environ.copy()
    merged.update(env)
    return subprocess.run(
        [zsh, "-c", script],
        cwd=ROOT,
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


def run_fcom(data: bytes, backup: Optional[bytes] = None) -> Tuple[subprocess.CompletedProcess, bytes, Optional[bytes]]:
    with tempfile.TemporaryDirectory(prefix="phase2a-fcom-") as temp:
        game = Path(temp)
        setup = game / "setup.exe"
        backup_path = game / "setup.exe.orig-backup"
        setup.write_bytes(data)
        if backup is not None:
            backup_path.write_bytes(backup)
        proc = run_zsh(step8_block(), {"GAME_DIR": str(game)})
        final = setup.read_bytes()
        saved_backup = backup_path.read_bytes() if backup_path.exists() else None
        return proc, final, saved_backup


def test_fcom_states() -> None:
    block = step8_block()
    require(block.index("site_a =") < block.index("shutil.copy2"), "FCOM backup occurs before both sites are classified")
    require(block.index("site_b =") < block.index("setup.write_bytes"), "FCOM target write occurs after Site B classification")
    require("zero writes and no backup creation" in block, "FCOM unknown-state abort is not documented")
    require("expected_offsets" in block and "final != bytes(expected)" in block, "FCOM exact-diff verification is missing")

    original = fixture_binary(A_UNPATCHED, B_UNPATCHED)
    proc, final, backup = run_fcom(original)
    require(proc.returncode == 0, f"valid unpatched FCOM case failed: {report_process(proc)}")
    require(backup == original, "valid unpatched case did not preserve the original backup")
    changed = {i for i, (before, after) in enumerate(zip(original, final)) if before != after}
    require(changed == EXPECTED_CHANGED, f"valid unpatched changed offsets were {sorted(changed)}")
    require(final[A_OFFSET:A_OFFSET + 1] == A_PATCHED, "Site A final byte is wrong")
    require(final[B_OFFSET:B_OFFSET + 4] == B_PATCHED, "Site B final bytes are wrong")

    patched = fixture_binary(A_PATCHED, B_PATCHED)
    proc, final, backup = run_fcom(patched)
    require(proc.returncode == 0, f"already-patched case failed: {report_process(proc)}")
    require(final == patched, "already-patched case modified the target")
    require(backup is None, "already-patched case created a backup")

    cases = {
        "Site A unknown": fixture_binary(b"\x00", B_UNPATCHED),
        "Site B unknown": fixture_binary(A_UNPATCHED, b"\x00\x00\x00\x00"),
        "mixed state": fixture_binary(A_PATCHED, B_UNPATCHED),
        "truncated target": b"\x00" * (B_OFFSET + 2),
    }
    for name, data in cases.items():
        proc, final, backup = run_fcom(data)
        require(proc.returncode != 0, f"{name} unexpectedly succeeded: {report_process(proc)}")
        require(final == data, f"{name} modified target bytes")
        require(backup is None, f"{name} created a backup despite fail-closed abort")

    preserved = bytearray(original)
    preserved[-1] ^= 0xFF
    proc, final, saved_backup = run_fcom(original, bytes(preserved))
    require(proc.returncode == 0, f"existing-backup case failed: {report_process(proc)}")
    require(saved_backup == bytes(preserved), "existing original backup was overwritten")
    require(final != original, "existing-backup case did not patch the target")


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
    allowed = {"SKILL.md", "tests/README.md", "tests/phase2a.py"}
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
        paths.add(value.strip('"'))
    require(paths <= allowed, f"unexpected changed paths: {sorted(paths)}")


def run_all() -> int:
    tests = (
        ("F-01 verify-only boundary", test_verify_only_boundary),
        ("F-02 FCOM fail-closed procedure", test_fcom_states),
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
