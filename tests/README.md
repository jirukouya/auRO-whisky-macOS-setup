# Phase 2A regression harness

Run from the repository root:

    python3 tests/phase2a.py --run
    python3 -m unittest discover -s tests -p 'test_*.py'
    python3 tests/test_whisky.py
    python3 -m py_compile tests/phase2a.py
    git diff --check

The production read-only health route accepts only explicit paths:

    python3 scripts/uaro.py doctor --game-dir "$GAME_DIR"
    # Optionally add: --apps-dir "$APPS_DIR" --settings-runtime-dir "$SETTINGS_RUNTIME_DIR"

The two optional flags may be omitted when those explicit paths are unavailable.
It reports structural/local-artifact facts and keeps execution, behavior, and
patch freshness unconfirmed. Its Settings runtime check is static-only and
does not execute the manifest interpreter. It never performs repair, launch,
download, signing, or deletion.

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
F-05, and F-06. Phase 2C's AzzyAI replacement boundary has a separate direct
test suite:

    PYTHONDONTWRITEBYTECODE=1 python3 -B tests/test_azzyai.py

That suite uses a project-authored synthetic USER_AI tree plus temporary copies
and tampered variants. The metadata-only
`tests/fixtures/azzyai-dc014477.manifest.json` records the reviewed pinned
upstream tree facts and is checked against the canonical production tree
identity; it is review evidence, not runtime policy. The synthetic tree tests
the same production verifier across nested files, binary-shaped and PDF-shaped
entries, missing entries, extra entries, byte changes, and symlinks. No
verbatim upstream AzzyAI source, binary, documentation, or
other USER_AI bytes are tracked.

The suite does not invoke Whisky, Wine, uaRO, a real launcher, or a deletion
command. F-04 network acquisition and signer provenance, plus Phase 2D, remain
outside this harness. A maintainer may independently extract the pinned
upstream commit and pass that path to the existing `verify-source` command for
optional integration evidence; ordinary tests remain offline and deterministic.
Successful CLI replacement also exercises the small descriptive JSONL evidence
sidecar; the sidecar is not read by the replacement gate. Tests also inject
evidence-write failures to confirm backup CLI failure status and restoration
after a post-exchange append failure.

`test_engineering_control.py` covers the Phase 0 control plane with temporary
Git fixtures. It exercises exact checkpoints, explicitly verified descendants,
scoped dirty children, unrelated dirty state, volatile-state boundaries, and
Phase Envelope validation. These tests prove repository control semantics only;
they do not prove a live Whisky/Wine installation or any external service.

The Whisky trust-boundary tests verify the fixed 2.3.5 source identity and
SHA-256 content policy anchored to an immutable Homebrew cask revision. They
reject mutable sources, wrong bytes, symlinks, malformed policy, mutated policy
constants, and candidate-supplied trust values; they also guard the documented
fail-closed extraction sequence.

## Continuous integration

Pull requests and pushes to `main` run the same repository-native deterministic
checks on a macOS runner through `.github/workflows/verify.yml`: Python
compilation, the standard-library unit suite, the Phase 2A harness, the
Whisky and AzzyAI suites, and `git diff --check`. A green workflow proves
those checked-in mechanisms on the runner; it does not prove a live
Whisky/Wine/game launch, external provenance, account state, or any other
machine-specific behavior.
