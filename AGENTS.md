# uaRO repository root contract

This is the project-specific entrypoint for a fresh Codex or Claude session.
It stays intentionally small. The detailed install and repair HOW lives in
`SKILL.md`; project history and the four documentation surfaces are indexed by
`CLAUDE.md`.

## Bootstrap

1. Confirm the repository root, `origin`, branch, `HEAD`, worktrees, and
   porcelain status before any mutation.
2. Read this file and `CLAUDE.md`; read only the relevant sections of
   `SKILL.md`, `TROUBLESHOOTING.md`, or `AZZYAI_FIXES.md` for the bounded goal.
3. Use `scripts/engineering_control.py reconcile` when a volatile state cache
   or Phase Envelope is present. A cache is evidence and recovery acceleration;
   Git, this contract, production code, and direct tests remain authoritative.

The canonical repository origin for this project is
`https://github.com/jirukouya/auRO-whisky-macOS-setup.git`; a different origin
is an identity failure and blocks reconciliation.

## Authority map

- **Policy and scope:** the current human-approved Phase Envelope.
- **Deterministic mutation HOW:** the production route in `SKILL.md` and the
  explicit-path executor in `scripts/uaro.py`.
- **Verification:** direct production tests plus an independent read-only
  verifier. Tests and cached evidence do not grant mutation or deletion
  authority.
- **Destructive authority:** an explicit human decision at the uninstall or
  other irreversible boundary.
- **Trust policy:** the current canonical trust contract and its direct
  evidence. A manifest, hash, signature, or old evidence record is not a trust
  root by itself.

## State and bounded phases

The control-plane script only captures evidence, reconciles an expected parent
against actual Git state, and validates the required Phase Envelope fields.
Use a volatile state file outside this repository. Never reset, restore, stash,
clean, push, merge, or modify `main` merely to make stale prompt assumptions
fit the checkout. Classify newer descendants before adopting them. Preserve
unrelated dirty work and stop mutation when state is ambiguous.

Every consequential phase must name its repository identity, branch, parent
`HEAD`, authorized files and capabilities, forbidden scope, frozen invariants,
worktree policy, required evidence and tests, independent verification,
rollback boundary, and one of the five terminal states defined by the program.
A phase commit is local unless the human grants new remote or integration
authority.

## Architecture Advisor boundary

Use the continuing architecture Advisor only for an architecture gap, semantic
gap, authority conflict, trust-anchor choice, cross-domain change, unresolved
false-completion challenge, phase acceptance, or final acceptance. Routine Git,
syntax, fixture, and known contract work stays in the inner engineering loop.

When the boundary is reached, send a compact packet containing:

```text
PROGRAM
CURRENT PROGRAM PHASE
CURRENT BOUNDED PHASE
PHASE GOAL
REPOSITORY / BRANCH / PARENT HEAD / CURRENT HEAD
WORKTREE STATE
AUTHORIZED SCOPE
FROZEN INVARIANTS
WHAT CHANGED
COMPLETED POSTCONDITIONS
FAILED / UNKNOWN
DIRECT TEST EVIDENCE
ADVERSARIAL EVIDENCE
INDEPENDENT VERIFIER RESULT
TRUST / AUTHORITY EFFECT
LIVE UNCONFIRMED CLAIMS
ROLLBACK BOUNDARY
FALSE-COMPLETION RISKS
DEFERRED FINDINGS
LUNA ASSESSMENT
ADVISOR DECISION REQUEST
```

Advisor output is architectural intelligence, not repository ground truth.
Root must validate any directive against the current checkout, canonical
contracts, and deterministic evidence before adopting it.

## Frozen project invariants

- `SKILL.md`, `README.md`, and `TROUBLESHOOTING.md` remain free of Chinese
  characters.
- Existing deterministic executor boundaries and fail-closed behavior remain
  intact unless a later bounded phase explicitly changes them.
- Live machine behavior, external network state, credentials, Keychain/TCC,
  and installed runtime state are never claimed from structural evidence.

## Entry points

```text
scripts/engineering_control.py snapshot --repo .
scripts/engineering_control.py reconcile --repo . --state-file <outside-repo.json>
scripts/engineering_control.py envelope validate --repo . --file <envelope.json>
scripts/engineering_control.py state init --repo . --state-file <outside-repo.json> --program-goal "<goal>" --phase <phase> --next-action "<action>"
scripts/engineering_control.py state update --repo . --state-file <outside-repo.json> [--phase-state <state>] [--last-verified-head <commit>]
```
