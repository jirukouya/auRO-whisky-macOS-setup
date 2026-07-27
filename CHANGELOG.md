# Changelog

All notable changes to this skill are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows [Semantic Versioning](https://semver.org/) in spirit — MINOR bumps for new fixes/behavior, PATCH bumps for wording/doc-only corrections. Since this repo ships a procedure, not an API, "breaking change" isn't really applicable; a 1.0.0 will mark the install process being considered fully stable (no known open issues left).

## [Unreleased]

## [0.6.0] - 2026-07-27

### Changed
- `uaro-cli repair` now actually diagnoses before it fixes, instead of blindly re-running `codesign`/`lsregister` regardless of whether anything was wrong. It checks the game install and bottle exist, then per launcher: executable bit, script syntax (`zsh -n`), whether the script predates the `command -v whisky` fallback fix, `Info.plist` validity, and reads back the real signature/registration state after attempting to fix it. Mechanical issues (permissions, signature, registration) get auto-fixed; anything else (bad syntax, a stale pre-fix script, a broken plist, a missing bottle) is flagged with a pointer back to Step 11 instead of being silently guessed at.

### Fixed
- Symptom: testing the new diagnostic loop against all three launchers showed a stray line like `exe_name=uaro-patcher` printed to output before the second and third launcher's checks — looked like a leaked debug print, though the checks themselves still ran against the correct files each time.
- Root cause: `local exe_name plist="..."` was declared fresh on every loop iteration. zsh's `local`/`typeset`, when given a bare variable name (no `=`) that already holds a value from a prior declaration in the same scope, prints `name=value` as a query instead of silently redeclaring it — confirmed by isolating the exact pattern in a standalone repro before touching the real script.
- Fix: declare `local exe_name` once, before the loop, and assign it via the `case` statement only (no `local` keyword) on each iteration. Verified clean output across all three launchers afterward, then separately verified the auto-fix path itself by deliberately `chmod -x`-ing a launcher's executable, running `uaro-cli repair`, and confirming both the `[FIXED]` line and the actual restored executable bit on disk.

## [0.5.0] - 2026-07-27

### Added
- New optional `uaro-cli` command-line helper, built as part of Step 11: `uaro-cli kill` (force-quit stuck uaRO/Wine processes), `uaro-cli launch` (open `UaRO Patcher.app`), `uaro-cli repair` (re-sign + re-register all installed launcher `.app` bundles). Installed directly to `/opt/homebrew/bin/uaro-cli` — already on `PATH` since Step 1, no shell-profile edit needed.
- Step 2a now offers to add `uaro-cli` to existing installs that predate this version — no consent-gating needed the way `UaRO Game.app` requires, since this carries no accepted risk of its own.
- Prompted by a suggestion from Discord contributor jax (add `~/.zshrc` aliases for the same three operations, optionally split across multiple skills). Kept the convenience, declined the `~/.zshrc`/multi-skill-file parts of the suggestion — see the new section's own explanation for why (global unversioned config mutation, shell-specific, conflicts with this repo's single-self-contained-file design). Verified all three subcommands on a real machine (kill/repair both confirmed working; launch uses the same `open` call already relied on elsewhere in this skill).

### Fixed
- Uninstall Level 1 was silently leaking the downloaded/extracted uaRO installer (`~/Games/UaRO_Setup.zip` + `~/Games/UaRO_Setup/`, ~4.7GB+ combined) on every uninstall — found while auditing whether this version's launcher renames/`uaro-cli` addition were fully reflected in the Uninstall section (they were), but that audit surfaced this separate, pre-existing gap: those two paths sit as siblings of `$GAME_DIR`, not inside it, so `rm -rf "$GAME_DIR"` never touched them. Now explicitly removed and verified in Level 1.

## [0.4.0] - 2026-07-27

### Added
- New third launcher, `UaRO Game.app` — skips `UaRo Patcher.exe` entirely and launches `uaRO.exe` directly, for a faster relaunch. Confirmed on one real machine to launch cleanly and reach a working login, but only tested on a bottle already fully up to date.
- Step 2a now offers to add `UaRO Game.app` to existing installs that predate this version, but only with explicit user consent — its risk is not something to accept on the user's behalf.

### Known limitation (documented, not fixed)
- `UaRO Game.app` has no way to detect whether the game client is stale relative to the server, since it never talks to the patcher. If a patch ships and this bottle hasn't run `UaRO Patcher.app` since, this launcher will silently launch whatever's on disk. See SKILL.md's Known open issues and Common Gotchas for the full writeup and the recommended mitigation (run the Patcher periodically).

### Fixed
- Cold-read review (fresh-agent pass with no prior context, same pattern as earlier cold-reads) caught real gaps introduced by this session's renaming/three-launcher work: two stale "two launcher(s)" wording leftovers, an incomplete `Info.plist` mirroring instruction that dropped `CFBundleDisplayName` (would leave all three bundles displaying "UaRO Patcher" in Finder regardless of which is open), and all three launcher scripts hardcoding `/opt/homebrew/bin/whisky` with no fallback for the case where Whisky was sideloaded via Step 3's GitHub-release fallback path (no `/opt/homebrew` symlink exists in that case) — now resolved via the same `command -v whisky || echo .../WhiskyCmd` pattern Step 3/5 already use.

## [0.3.0] - 2026-07-27

### Changed
- Renamed the patcher launcher from plain `UaRO.app` to `UaRO Patcher.app` (bundle, `Info.plist` fields, and internal script `uaro-launch` → `uaro-patcher`), so its name describes what it actually does, matching `UaRO Settings.app`'s naming pattern. `UaRO Settings.app` itself is unchanged.
- Added a Step 2a migration check: an existing install still carrying the old `UaRO.app` name gets renamed (bundle + `Info.plist` + script + re-sign + re-register) instead of being left half-migrated.

### Added
- Documented the migration path explicitly in Step 11's own notes, so a future edit to the launcher doesn't accidentally reintroduce the old name.

## [0.2.1] - 2026-07-27

### Changed
- Added a Table of contents (anchor-linked) near the top of `SKILL.md`, splitting it into "Setup" (the linear, execute-in-order steps) and "Reference" (Known open issues, Common Gotchas, Uninstall, Credits — consulted as needed, not part of the install sequence).
- Moved Step 9b (menu-shortcut keybind fix) back to its correct numerical position, right after Step 9 — it had been appended after "Known open issues" when first added, out of sequence with the rest of the steps.
- Tagged every entry in "Known open issues" and every row of "Common Gotchas" with a `Category` (`Input/Keyboard`, `Crash/Gameplay`, `Runtime/Wine`, `Launcher/Signing`, etc.) so both a human skim and an AI keyword search can jump straight to the relevant rows instead of scanning the whole table.
- No functional/procedural content changed — this is a pure findability/navigation pass, prompted by `SKILL.md` growing large enough that locating a specific step or gotcha by scrolling alone was getting slower than it should be.

## [0.2.0] - 2026-07-26

### Fixed
- In-game menu shortcuts (`Cmd+A`, `Cmd+Z`, etc.) not registering — game shortcuts now go through `Option` (mapped to Alt via Wine's `LeftOptionIsAlt`/`RightOptionIsAlt`), matching how uaRO already behaves in a Windows VM. This replaces an earlier approach (disabling Wine's hidden macOS Edit menu) that fixed the same symptom but broke native `Cmd+V` paste as a side effect — the new approach has no such trade-off.
- "Program Error" crash dialog appearing after the post-Gecko patcher launch — mitigated (not root-caused) by suppressing Wine's crash dialog (`ShowCrashDialog=0`) combined with a bounded single-retry watchdog in the launcher script.

### Added
- Step 2a now also detects bottles still running the old Edit-menu-disable fix (and migrates them) or missing the new Option/Alt fix entirely, and separately detects launchers missing the crash-dialog mitigation.
- Step 12 first-run checklist now tells the user the game's Alt key is macOS's Option key.
- "Known open issues" documents the precise trigger sequence found for the post-Gecko patcher crash (a likely Gepard anti-debug self-check breakpoint mishandled by Wine's exception dispatch), for anyone who wants to dig into the real root cause later.

## [0.1.0] - 2026-07-25

Initial public release. A single self-contained `SKILL.md` that installs uaRO on Apple Silicon Macs via Whisky, end to end, meant to be handed to a fresh Claude Code/Codex session with no other context.

### Added
- Steps 1–12: Homebrew → Rosetta 2 → Whisky.app → WhiskyWine runtime → bottle creation/config → download & run the uaRO installer → FCOM byte-patch for Rosetta compatibility → Wine Gecko pre-install → game config files → two launcher `.app` bundles (with icon extraction) → first-run verification.
- Pre-flight checks: Apple Silicon gate, macOS version gate, disk space check.
- Environment-adaptive detection/self-heal: existing-state scan (Step 2a), proactive installer-download handling (Step 2b) with iCloud-relocation avoidance and size-stability recheck.
- Mandatory verification after every risky step (byte-diff after binary patches, decode-testing config files, `lsregister -dump` after building launchers) instead of trusting exit codes alone.
- Per-step progress table with explicit user approval gate before advancing to the next step.
- Uninstall/rollback section with tiered levels and backup-dependency warnings.
- `caffeinate -i` wrapping around long unattended waits so macOS idle sleep doesn't stall the install.
- README: project story (VMware/Gepard dead end, why Whisky needed real bug-fixing to work), how-to-run instructions, Credits & Disclaimer, MIT LICENSE.
