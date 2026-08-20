# Project knowledge map

This file is an index, not content. Its only job: tell any reader (a fresh
Claude Code/Codex session, the maintainer months from now, or an external
contributor) where the actual information lives, so nothing gets missed by
relying on memory alone.

**Rule: before answering any "what have we already done / dealt with /
decided about X" question for this project, check all four sources below —
not just one or two.**

## The four places change history lives

1. **`git log` (commit messages)** — the most granular record, tied to each
   diff. Bug-fix/investigation commits should follow a
   Symptom / Ruled out / Root cause / Fix body structure (not just a
   one-line summary) — see the two best examples: commits `38092d5` and
   `c1db2eb`.

   **Also check `git notes`** (`git log --show-notes`, or
   `git notes show <hash>`) — 13 older commits that predate this
   commit-message framework had that same Symptom/Ruled out/Root
   cause/Fix detail retroactively attached as notes instead of rewriting
   already-pushed history. **Notes don't show up in a plain `git log` or
   a fresh `git clone`/`git fetch`** — the ref (`refs/notes/commits`)
   has to be fetched explicitly:
   `git fetch origin refs/notes/commits:refs/notes/commits`, then
   `git log --show-notes`. Easy to forget this ref exists at all if you
   don't already know to look for it — which is exactly the kind of gap
   this file exists to close.

2. **`CHANGELOG.md`** — curated, per-version (Keep a Changelog format),
   human-facing "what changed and why" summary. This is the closest
   equivalent to a traditional changelog/troubleshooting summary — check it
   whenever comparing "what do we already have" against an external log or
   report.

3. **`SKILL.md`** (each step's mandatory verification blocks) and
   **`TROUBLESHOOTING.md`** ("Known open issues" + the Common Gotchas table,
   split out of `SKILL.md` at v0.19.0 — see "Standing constraints" below).
   Together these are the *living* current-state doc: symptoms,
   verification methods, and anything still unresolved. If a question is
   "is this still broken / how do we verify this," this is the first place
   to check, since it's the only layer that's actively kept in sync with
   the live install process.

4. **Claude's persistent memory** (not part of this git repo at all — lives
   at `~/.claude/projects/-Users-derekho/memory/` on the maintainer's
   machine, independent of any commit). Holds feedback/preference/decision
   history that isn't code or install-process content (e.g. why certain
   proposals were rejected, how to write commit messages). **A human reader
   of this repo — including an external contributor — cannot see this
   layer.** If something here matters to a human collaborator, it needs to
   also be written into CHANGELOG.md or SKILL.md, not left only in memory.

## Why four layers, not one

They're audience- and format-differentiated, not redundant: commit
messages carry diff-level diagnostic detail, CHANGELOG.md is the curated
version-level summary, SKILL.md is the live current-state doc, and Claude
memory is cross-session/cross-project context that has nothing to do with
git. Collapsing them loses real information rather than reducing effort —
the actual fix for "we forgot to check one" is this index, not fewer
places.

## Standing constraints on this project (don't relitigate these)

- **Two-file model (revised at v0.19.0 — see below for why this replaces
  the old single-file rule):** `SKILL.md` is the linear execution path —
  Steps 0–12 plus Uninstall must stay runnable end-to-end from this one
  file alone, handed to a fresh AI session with no other context. Grouping
  Steps 1–12 into five navigational "Phase" headers at v0.19.0 did not
  change this — phase headers don't gate reading, a fresh install still
  reads and runs every phase in order. `TROUBLESHOOTING.md` is
  symptom-indexed reference material (Known open issues + the Common
  Gotchas table) — consulted on a verification failure or a reported
  symptom, never read top-to-bottom, and never needed for a normal
  successful install. **This reverses the previous rule** ("`SKILL.md` must
  stay a single self-contained file — no `reference/` folder split"): that
  rule was written to prevent a fresh AI session from missing content it
  actually needs mid-install. Known open issues/Common Gotchas don't carry
  that risk — they're pure lookup-on-symptom content nothing in the linear
  path depends on — so splitting just them out doesn't reintroduce the
  problem the original rule was guarding against. A future session should
  not re-litigate this from a stale memory of the old rule.
- `SKILL.md`, `README.md`, and `TROUBLESHOOTING.md` must contain zero
  Chinese characters (verify with `grep -n "[一-龥]" <file>` after edits —
  exit 1 means clean).
- Solo-maintained; an external Discord contributor (jax) shares findings
  occasionally but doesn't have write access or visibility into Claude's
  memory layer above.
- A separate troubleshoot-log file (like jax's own `TROUBLESHOOTING_LOG.md`
  in his own workspace) was considered and rejected for this repo — it
  would be a second surface to keep in sync, and an uncurated timeline
  mixes abandoned dead-ends with the final decision at equal weight. Richer
  commit messages (point 1 above) were chosen instead.
