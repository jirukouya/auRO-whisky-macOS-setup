# Phase 2A regression harness

Run from the repository root:

    python3 tests/phase2a.py --run
    python3 -m py_compile tests/phase2a.py
    git diff --check

The harness uses Python's standard library only. It creates temporary fixtures
and never invokes Whisky, Wine, uaRO, a real launcher, or a deletion command.

The FCOM and savedata cases extract the actual shell/Python procedures from
SKILL.md and execute them against temporary files; the savedata route invokes
the deterministic `uaro.py backup savedata` executor. The uaro-cli cases extract
the embedded repair script, substitute only temporary fixture paths, and stub
whisky, codesign, plutil, and Launch Services commands.

The verify-only and execution-gate checks are structural and static because
SKILL.md is a Markdown playbook rather than an importable runtime module.
Those checks verify the documented boundary and evidence rules; they are not
runtime proof of a real macOS installation. Live execution evidence remains
UNCONFIRMED unless it is independently observable.

The harness intentionally covers only Phase 2A findings F-01, F-02, F-03,
F-05, and F-06. It does not implement Phase 2C or Phase 2D.
