---
name: auro-whisky-macos-setup
version: 0.21.0
description: Installs, verifies, repairs, and configures uaRO (a Ragnarok Online private server) on Apple Silicon macOS via Homebrew + Whisky + a manually-sourced WhiskyWine runtime. Use this skill for a fresh install, an existing or partial install, a verify-only health check, a repair of a known symptom, a migration to newer fixes, or an uninstall. Trigger on "install uaRO on Mac", "set up uaRO with Whisky", "check my uaRO Whisky install", "repair uaRO", "uaRO patcher stuck", "Gepard error on Whisky", "Program Error in uaRO", "uaRO keyboard or graphics issue", "whisky uaro install", or "uninstall uaRO". Do not use it for CrossOver, generic Wine troubleshooting, or unrelated Windows games.
---

# uaRO on macOS via Whisky — Full Install Skill

This file is meant to be handed to a fresh Claude Code (or Codex) session on a brand-new Mac, with no other context. Read it once, then execute Steps 1–12 in order. Every value needed to actually do the work is inlined below — nothing here requires fetching an external reference doc first.

This is not a rewrite from theory. It is the corrected, verified procedure after actually running the whole thing once on a real machine (Apple Silicon, macOS 26.5.2) and finding several real bugs in the "obvious" version of these steps. Every mandatory verification step below exists because skipping it once actually produced a silent failure during that run — they are not defensive-programming boilerplate.

## Table of contents

**Two separate numbering schemes appear below, on purpose — don't conflate them:** `1. Parameters`/`2. Pre-flight`/`2a`/`2b` are one-time setup/detection sections that run *before* the linear install begins; `Step 1` through `Step 12` are the install sequence itself, grouped into five phases (A–E) purely for navigation — the phase headers don't rename or renumber any step, and every cross-reference elsewhere in this file still says "Step N", not "Phase X". `2. Pre-flight` and `Step 2` are unrelated despite the shared digit. **`1a` deliberately comes before `1` in reading order**, not after — Section 0 tells you to post the progress table "(format below)" before you've seen it once, so `1a` shows that format immediately, ahead of `1. Parameters`, rather than leaving it to be found later.

[**Quick routing — where do I start?**](#quick-routing--where-do-i-start) Read this first — it tells you which part of this file actually applies to this session, before you commit to reading the whole thing top to bottom.

**Setup (execute in order, once):**
[0. Operating principles](#0-operating-principles--read-before-starting) ·
[1a. Progress table](#1a-progress-table-post-this-updated-after-every-single-step) ·
[1. Parameters](#1-parameters-decide-these-fresh-every-machine) ·
[2. Pre-flight](#2-pre-flight) ·
[2a. Detect existing state](#2a-detect-existing-state-before-step-3--different-machines-start-from-different-points) ·
[2b. Kick off installer download](#2b-kick-off-the-uaro-installer-download-now--dont-wait-until-step-6)

**Phase A — Environment prep:**
[Step 1 — Homebrew](#step-1--homebrew) ·
[Step 2 — Rosetta 2](#step-2--rosetta-2-apple-silicon-only) ·
[Step 3 — Whisky.app](#step-3--whiskyapp) ·
[Step 4 — WhiskyWine runtime](#step-4--whiskywine-runtime-wine-7x--apple-gptk--dxvk)

**Phase B — Bottle & game install:**
[Step 5 — Bottle create/config](#step-5--create--configure-the-bottle) ·
[Step 6 — Download & extract installer](#step-6--download--extract-the-uaro-installer) ·
[Step 7 — Run the installer](#step-7--run-the-installer) ·
[Step 8 — FCOM byte-patches](#step-8--patch-setupexe-fcom-byte-patches-two-sites)

**Phase C — Client readiness:**
[Step 9 — Wine Gecko pre-install](#step-9--pre-install-wine-gecko-mandatory-before-uaro-patcherapp-is-ever-launched) ·
[Step 9b — Fix menu-shortcut keybinds](#step-9b--fix-in-game-menu-shortcuts-cmdacmdz-style-not-registering) ·
[Step 10 — Game config files](#step-10--write-game-config-files)

**Phase D — Launchers & tooling:**
[Step 11 — Launcher .app bundles](#step-11--build-the-three-launcher-app-bundles) ·
[Optional: uaro-cli command-line helper](#optional-uaro-cli-command-line-helper)

**Phase E — Verify & wrap-up:**
[Step 12 — First-run verification](#step-12--first-run-verification-do-this-before-considering-the-install-done) ·
[Installation complete](#installation-complete--post-this-once-step-12-passes)

**Reference (consult as needed, not part of the linear install path):**
[Optional: AzzyAI](#optional-azzyai-mercenaryhomunculus-auto-attack-ai) — mercenary/homunculus auto-attack AI, full guide in `AZZYAI_FIXES.md` ·
[Troubleshooting reference](./TROUBLESHOOTING.md) — Known open issues + Common Gotchas table, tagged by Category, split into its own file at v0.19.0 ·
[Uninstall / rollback](#uninstall--rollback) ·
[Credits & Disclaimer](#credits--disclaimer)

## Quick routing — where do I start?

| This session's situation | Start here |
|---|---|
| Fresh install — this Mac has never run this skill before | The Setup section, top to bottom (`0` → `1a` → `1` → `2` → `2a` → `2b`), then Phase A → B → C → D → E in order |
| This Mac already ran this skill before — install may be partial, carried over from an earlier attempt, or missing a fix added since | Go straight to [2a. Detect existing state](#2a-detect-existing-state-before-step-3--different-machines-start-from-different-points) — it tells you exactly which step to resume from and whether anything needs retrofitting onto an existing install |
| Install already works, but hit a specific error or symptom | Check [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) first — most known symptoms are already indexed there by Category; only fall back to re-reading a Step in full if the symptom genuinely isn't covered there |
| Removing uaRO, or starting over from scratch | Skip straight to [Uninstall / rollback](#uninstall--rollback) — no need to read or touch anything above it first |

This table is a shortcut, not a replacement for the Setup section's own logic — 2a still does the real detection work; this table just points at which door to walk through first.

## 0. Operating principles — read before starting

> [!IMPORTANT]
> **The 5 rules most likely to silently break something if skipped — distilled from the full list below, not a replacement for it:**
> 1. **Check the real on-disk/registered state before installing, downloading, or provisioning anything** — never fire a mutating command unconditionally and parse errors after the fact.
> 2. **Never chain steps together.** Post the progress table and stop for explicit approval after every single step, even when it "obviously" succeeded.
> 3. **Angle-bracket placeholders (`<GAME_DIR>`, `<BOTTLE_NAME>`, etc.) must be substituted with real resolved values before writing them into anything that executes standalone later** — once baked into a script on disk, they are not live shell variables anymore.
> 4. **Shell variables don't reliably survive across separate tool calls.** Re-derive `$BOTTLE_NAME`/`$GAME_DIR`/`$WHISKY` (and any step-local variable) at the top of every block that uses them, even if it was "just set" a few blocks ago.
> 5. **Verify with the actual command output, not an exit code or "it should have worked."** A syntax-valid file isn't a working file, exit 0 isn't proof a cask actually installed anything, and silence after a patch isn't proof it applied correctly.

### Evidence-driven execution contract

Before touching the machine, choose exactly one route for this run:

| Route | Use when | Default behavior |
|---|---|---|
| `fresh` | No usable Whisky/uaRO state is present | Build only after pre-flight checks pass |
| `adopt` | A partial or older install already exists | Reuse verified state and retrofit only missing fixes |
| `verify` | The user asks whether an existing install works | Read and measure only; do not reinstall or rebuild |
| `repair` | A concrete symptom is reported | Identify the failing layer first, then make the smallest scoped fix |
| `uninstall` | The user wants uaRO or its dependencies removed | Resolve exact targets, back up saves, and use the recovery-first deletion flow below |

Maintain a short state ledger for the chosen route:

```text
target | current state | desired state | evidence | planned change | rollback
```

Treat instructions copied from another author, repository, or machine as **transcribed** until they are rerun on this Whisky target. A mechanism-based explanation is **inferred** until a test distinguishes it from competing explanations. Map these states to the host's fact-gate labels when reporting: `CONFIRMED`, `INFERRED`, `ASSUMED`, `UNCONFIRMED`, `CONFLICTING SOURCES`, and `BLOCKED`.

Every completion claim must pass three independent gates:

| Gate | What to prove | Whisky examples |
|---|---|---|
| Target | The intended file/config/backup exists at the intended path | `plutil -p`, `cmp`, `test -f`, byte diff |
| Execution | The actual process loads the intended bottle, environment, and runtime | `shellenv`, `WINEPREFIX`, process args, runtime path, relevant log |
| Behavior | The user's requested function works under the same route | Patcher advances, settings round-trip, login remains stable, no target symptom |

Passing only one gate is `UNCONFIRMED`, not complete. Startup alone is not a behavior test, and a generated launcher or manifest is not live-runtime evidence.

### Verify-only capability boundary (F-01)

When the route is verify, this skill authorizes evidence collection only:

- **Allowed:** read, inspect, query, hash, compare, and non-mutating process inspection.
- **Not authorized:** write, patch, install, delete, update, apply settings, registry writes, downloads, codesign, registration, automatic repair, or mutable patcher/game launch.

If stronger behavior evidence would require a mutating action, report UNCONFIRMED at that gate. Do not mutate the installation to turn UNCONFIRMED into PASS.

A command denylist is only a regression heuristic. It is not complete capability enforcement; the verify-only route still requires reviewing the actual commands and their observable effects.


- **Before answering any "what have we already tried/decided/fixed for this project" question — especially a comparative one, or one about a symptom that might already be a documented issue — read this repo's root `CLAUDE.md` first, then check every source it points to** (commit messages, `CHANGELOG.md`, `TROUBLESHOOTING.md`, and `git notes` — see `CLAUDE.md` for why notes need an explicit `git fetch` to even become visible). Don't answer from whichever one source happens to come to mind first; a past run of this exact skill answered a historical-comparison question from `git log` alone and missed that `CHANGELOG.md` had the closer answer. This applies to *any* agent executing this file, not just one with prior conversation context — that's the whole reason it's written here instead of only remembered.
- **Probe, don't assume, especially about what's "dead."** The premise "the Homebrew cask is disabled" turned out to be false on one real machine tested — it installed and worked fine. Try the normal path first every time; only fall back to a workaround if the normal path genuinely fails on *this* machine, right now.
- **Check the real on-disk/registered end-state before running an install or download command — don't fire it unconditionally and parse errors after the fact.** Steps 3 (Whisky.app), 4 (WhiskyWine runtime), and 9 (Wine Gecko) each learned this the hard way on real repeat/carried-over runs: an unconditional `brew install --cask whisky` threw noisy "not permitted" errors against an already-installed app, an unconditional runtime download re-fetched something already working, and an unconditional `winetricks -q gecko` made an already-installed Gecko look like an open question rather than a settled one. Apply the same check-first pattern to any future step that installs, downloads, or provisions something.
- **A syntax-valid file is not a working file.** `plutil -lint` only checks that a plist parses as XML — it says nothing about whether the app that reads it can decode it into the shape it expects. Decode-test configs, don't just lint them.
- **A file existing right after you wrote it is not proof it will still be there in 30 seconds.** On a Mac with iCloud Drive "Desktop & Documents" sync enabled, files written under `~/Documents` *and* `~/Downloads` can be silently relocated into `~/Library/Mobile Documents/com~apple~CloudDocs/...` asynchronously, tens of seconds after creation — long after an immediate check would have reported "fine."
- **After any binary patch, byte-diff against a backup.** Don't trust that a patch did only what you intended — prove it with `cmp -l`.
- **Never overwrite an original backup on a rerun.** Create `*.orig-backup` only when it is absent; if it already exists, preserve it and verify that the current target has the same size before patching. A backup made from an already-patched file is not a rollback point.
- **Do not silently merge an alternate runtime recipe into the default route.** If another guide proposes a different renderer, DLL override, sync mode, or Wine backend, record the current state, test it as an isolated diagnostic branch, and restore the standard route before comparing results.
- **`dd` writing to a binary file may be blocked in sandboxed/agent shells**, independent of file permissions. If it is, fall back to plain Python `open(path, 'r+b')` — it produces byte-identical results and isn't subject to the same restriction.
- **Never generate backslash-heavy config content through an unquoted heredoc** (`<< EOF`). Bash silently collapses `\\` pairs to `\` before the inner script even sees them. Always use a quoted delimiter (`<<'EOF'`) or write a real script file.
- **After every step, post the cumulative progress table (format below) and stop for explicit approval before touching the next step.** Never silently chain two steps together, even when a step "obviously" succeeded and even if the user seems to be in a hurry — this is the user's one visible checkpoint into a long, mostly-invisible process.
- **Angle-bracket placeholders (`<GAME_DIR>`, `<BOTTLE_NAME>`, `<UUID>`, `<CHOSEN_WIDTH>`, etc.) are not live shell variables — substitute the actual resolved value before writing them into anything that will execute standalone later** (the Python patch scripts, the three launcher `.app` scripts). This is different from an inline `$GAME_DIR` in a bash block meant to run immediately in this same shell. Code written to disk for later execution has no access to this session's variables — baking the literal text `<BOTTLE_NAME>` into a launcher script fails silently at write time and only breaks when the user actually double-clicks the app.
- **A different risk, easy to conflate with the one above: `$BOTTLE_NAME`, `$GAME_DIR`, `$WHISKY`, and other inline (non-placeholder) shell variables used directly in a bash block are not guaranteed to survive into a separately-run *later* block either.** Many agent tool-execution harnesses reset shell state between tool calls and only guarantee the working directory persists — a variable exported in one call is not reliably still set two calls later, even within the same Step. Prefer running each Step's full command sequence as one combined shell invocation so this never comes up. If your tooling forces a Step's commands across multiple separate calls anyway, re-derive/re-export the values a given block actually uses at the top of that block — don't assume something set several blocks ago is still there. See the callout right after the Parameters table below for the one-liners to re-derive the three most commonly reused ones (`$BOTTLE_NAME`, `$GAME_DIR`, `$WHISKY`); step-local variables (`$SETUP` in Step 8, `$META`/`$GUID` in Steps 5/10, `$SUPPORT` in Step 4, `$APPS` in Step 11, etc.) follow the same rule using that step's own definition line. `$APPS` specifically has a re-derivation one-liner of its own (right after Step 11's `mkdir` loop) that reads back a real on-disk fact (whether `/Applications/UaRO Game.app` exists) rather than trying to remember a yes/no answer given several blocks ago — prefer that pattern (checking something real on disk) over remembering a decision, wherever a step's later blocks can.
- **Some steps may trigger a macOS admin/login password prompt (`sudo`) — expected, not a sign of a hijacked machine.** Homebrew's installer (Step 1) commonly needs it the first time it creates `/opt/homebrew`; Rosetta (Step 2) occasionally does too. Warn the user *before* running that command that a password prompt may appear. If the shell running these commands has no interactive terminal attached, the prompt can't be answered programmatically at all — it will hang or fail outright (`sudo: a password is required`) instead of actually showing a box to type into. If that happens, tell the user to open a normal Terminal window themselves and run that one command directly — only they should ever type their own Mac password, never ask them to tell it to you.

## 1a. Progress table (post this, updated, after every single step)

Repost the **whole table**, not just the changed row, so the user always sees the full run at a glance:

**Note on the two numbering schemes in this row column:** rows labeled bare `2a`/`2b` refer to the setup sections of those exact names (which run *before* `Step 1`, per the document's own top-to-bottom order); every other row is a `Step N` from the linear install sequence, labeled `Step N` here specifically so it can't be misread as the *different*, similarly-numbered `1. Parameters`/`2. Pre-flight` sections earlier in this file — those two aren't tracked in this table at all, since they're one-time decisions/checks, not steps with their own pass/fail state.

| Step | What it does | Status | Notes |
|---|---|---|---|
| 2a | Detect existing state | ✅/❌/— | |
| 2b | Kick off installer download | ✅/❌/— | |
| Step 1 | Homebrew | ✅/❌/— | |
| Step 2 | Rosetta 2 (Apple Silicon only) | ✅/❌/—/N/A | |
| Step 3 | Whisky.app | ✅/❌/— | |
| Step 4 | WhiskyWine runtime | ✅/❌/— | |
| Step 5 | Bottle create/config | ✅/❌/— | |
| Step 6 | Download & extract installer | ✅/❌/— | |
| Step 7 | Run installer | ✅/❌/— | |
| Step 8 | FCOM byte-patches | ✅/❌/— | |
| Step 9 | Wine Gecko pre-install | ✅/❌/— | |
| Step 9b | Fix game menu shortcuts (Option=Alt) | ✅/❌/— | |
| Step 10 | Game config files | ✅/❌/— | |
| Step 11 | Launcher `.app` bundles + icon | ✅/❌/— | |
| Step 12 | First-run verification | ✅/❌/— | |

Rules for filling it in:
- **✅** — state *how* it was verified (the actual command/output checked), not just "done". E.g. "`wine64 --version` → `wine-7.7`", not "installed".
- **❌** — never leave this bare. The Notes cell must give exactly ONE recommended next action, chosen for *this* machine's actual detected environment (chip from `uname -m`, macOS version from `sw_vers`, what Pre-flight found already installed, what the real error text said) — not a generic list of possible causes. If genuinely unsure, say so plainly and propose the one action that would disambiguate it, rather than guessing.
- **—** — not attempted yet this run. Don't mark a step ❌ preemptively just because it's later in the sequence.
- **N/A** — doesn't apply to this machine (e.g. Step 2 on Intel Macs).
- After posting the table, stop and ask explicitly, e.g. *"Step N looks good — take your time, and let me know when you're ready for Step N+1."* (or, on a ❌ row, *"Want me to apply the fix above before continuing?"*). Wait for the user's actual reply. Do not treat silence, a prior unrelated "yes," or your own confidence that it'll work as approval.

## 1. Parameters (decide these fresh, every machine)

| Parameter | Default | Notes |
|---|---|---|
| `BOTTLE_NAME` | `uaro` | Resolve the *real* on-disk UUID freshly via `whisky list` every time — never hardcode a UUID across machines. |
| `GAME_DIR` | `$HOME/Games/UaRO World of Your Dream` | Must NOT be under `~/Desktop`, `~/Documents`, or `~/Downloads` — see the iCloud gotcha below. `~/Games/<name>` or `~/Library/Application Support/<vendor>/<name>` are both confirmed-safe locations. |
| `RESOLUTION` | closest available in RO OpenSetup's dropdown | Do not hardcode a pixel value — RO OpenSetup (`setup.exe`) offers a fixed list of scaled resolutions derived from the actual display's native resolution/scale factor. **Detect this machine's actual display first** (`system_profiler SPDisplaysDataType \| grep Resolution`), then offer that as the recommended default when asking the user, rather than asking with no context. The line it prints looks like `Resolution: 3456 x 2234 Retina` — the two bare integers either side of the `x` are the width and height to use wherever this file asks for `<CHOSEN_WIDTH>`/`<CHOSEN_HEIGHT>` (e.g. `3456` and `2234`; ignore the trailing `Retina`/`Main Display` words, and use just the first display line if the machine has more than one). Pick the closest same-aspect-ratio entry from the real dropdown once you get to Step 12 — different Macs have different native/scaled resolution lists, so the "right" answer genuinely varies by machine. |
| `INSTALLER_SOURCE` | ask the user / check `~/Downloads` and common game folders, detected **by file size, not filename** (see 2b) | Could be a local `.zip` already downloaded, or a URL the user provides. Never guess/fabricate a download URL yourself. The installer itself sits behind a login wall (`https://uaro.net/cp/?module=account&action=login` — user-provided, not something you can fetch on their behalf), so this is always a human-driven download, never one you can script end-to-end. |

> [!TIP]
> **Prepend these three lines to the start of every code block from Step 4 onward that touches `$BOTTLE_NAME`/`$GAME_DIR`/`$WHISKY`, every single time — don't try to judge whether this happens to be the same shell invocation that last set them.** That judgment call is exactly the failure mode this callout exists to remove: reassigning an already-correct value is a harmless no-op, so there's no cost to always doing it, only a cost to skipping it and guessing wrong (see Section 0's note on shell-state not persisting across separate tool calls, and Step 11's `$APPS`/`$EXE` blocks for the same idea applied to that step's own variables).
> ```bash
> BOTTLE_NAME="uaro"                                              # or whatever was actually decided for this machine
> GAME_DIR="$HOME/Games/UaRO World of Your Dream"                 # the real value decided in Section 1 (Parameters)
>                                                                  # above -- not "Step 1", see the Table of Contents
>                                                                  # note on the two numbering schemes -- OR, if
>                                                                  # Step 7 found the installer
>                                                                  # wrote somewhere else, the real adopted path from
>                                                                  # there instead. Never paste this literal default
>                                                                  # without checking which one actually applies.
> WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
> ```

## 2. Pre-flight

```bash
sw_vers
uname -m                                  # arm64 = Apple Silicon, needs Rosetta (Step 2); anything else = Intel, see below
defaults read com.apple.finder FXICloudDriveDesktop FXICloudDriveDocuments 2>/dev/null
df -h /                                   # need roughly 15-20GB free — see below
```

**Check free disk space before going any further.** Between the uaRO installer itself (~4.7GB download, more once extracted), the WhiskyWine runtime, and the various `.orig-backup` copies this process keeps for safety, plan on needing roughly **15-20GB free** on the boot volume. If `df -h /` shows meaningfully less than that available, tell the user now, plainly — e.g. *"Heads up — this install needs about 15-20GB of free space, and this Mac currently has [X]GB available. Worth freeing up some space (Trash, old downloads, etc.) before we start, since running out partway through tends to show up as a confusing partial-download or partial-extraction failure rather than a clear error."* Don't let a low-space machine run silently into Step 6/7 and discover it there.

**Stop here if `uname -m` did not print `arm64`.** Whisky was built specifically for Apple Silicon — confirmed directly: the actual `Whisky.app` binary is Mach-O `arm64` only (no Intel slice), and Whisky's own Homebrew cask metadata declares `arch: arm64` as a requirement. Because of that, there isn't an Intel-compatible path through this particular skill. If this machine reports `x86_64` (or anything other than `arm64`), let the user know kindly before touching Step 1, e.g.: *"Quick heads-up — Whisky, the tool this install relies on, was built specifically for Apple Silicon Macs (M1 and later). This Mac has an Intel chip, so this particular skill isn't the right fit here."* Then hold off on Step 1 and the rest until the user's decided how they'd like to proceed.

**Also check the macOS version from `sw_vers` against Whisky's other stated requirement — macOS 14 (Sonoma) or newer.** This comes from the same cask metadata as the `arm64` requirement above (`{'macos': {'>=': ['14']}, 'arch': [...]}`), so it's just as real, even on an otherwise-compatible Apple Silicon Mac. If the version is older than 14, give the user the same kind of gentle heads-up before Step 1, e.g.: *"One more thing — Whisky officially needs macOS 14 (Sonoma) or newer, and this Mac is currently on [version]. Might be worth updating macOS first, if that's an option here."* Then pause for the user rather than pushing ahead into a cask install that may simply refuse to run. **Don't read a big-looking version jump as a compatibility red flag** — a real install confirmed this works fine on macOS 26 (Tahoe); Apple's own numbering (14 → 15 → 26) skipped ahead, but "14 or newer" still means exactly that.

The iCloud check above tells you if the *official* toggle is on. Treat a "1" as a strong warning. **Treat a missing/0 result as inconclusive, not as proof of safety** — `~/Downloads` was affected on a real machine despite not being one of the two officially-named folders. The only real safety net is the write-then-wait-then-recheck step in Step 6, not this probe.

## 2a. Detect existing state (before Step 3 — different machines start from different points)

Not every machine this runs on is a truly blank slate — Whisky, a bottle, or even a partial/full uaRO install may already exist from a previous attempt. Check before assuming Step 3 onward all need to run from zero:

```bash
# Existing Whisky.app / CLI?
ls -d /Applications/Whisky.app ~/Applications/Whisky.app 2>/dev/null
command -v whisky

# Existing bottles, and does any of them already have wine64?
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
"$WHISKY" list 2>/dev/null

# Existing uaRO install anywhere plausible — common host paths, plus inside every bottle's drive_c
find ~/Games ~/Documents ~/Downloads ~/"Library/Application Support" -maxdepth 3 -iname "UaRO*" -type d 2>/dev/null
find ~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/*/drive_c -maxdepth 3 -iname "UaRO*" -type d 2>/dev/null
```

**If a bottle already exists, also check whether it's missing (or carrying an outdated version of) any fix added to this skill since it was created** — don't wait for the user to describe a symptom before mentioning it. Right now that means Step 9b's keybind fix; substitute the real bottle name for `$BOTTLE_NAME`:

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
command -v wine64 >/dev/null || echo "runtime not linked yet — skip this check, Step 5 will sort it out"
EDITMENU=$(wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu 2>/dev/null)
OPTALT=$(wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt 2>/dev/null)
```

Two independent things to check here:

- **`$EDITMENU` has any output at all (even an empty value)** → this bottle has the *old*, superseded version of Step 9b applied (the one that disabled the hidden Edit menu). Tell the user plainly: *"Heads up — this uaRO install has an older fix applied that trades away native Cmd+V paste. There's a better fix now that doesn't have that trade-off. Want me to switch it over? Requires fully closing the game first."* If yes, apply the migration + current Step 9b.
- **`$OPTALT` is empty** → Step 9b (current version) was never applied at all. Tell the user plainly, even if they never mentioned a keybind problem: *"Heads up — this uaRO install was set up before a keybind fix was added to this skill. In-game menu shortcuts (like opening the item window) probably don't work correctly right now. Want me to apply that fix now? It's quick, but does require fully closing the game first."* Apply Step 9b if they say yes, then continue with whatever else this run was for.
- **If `/Applications/UaRO.app` exists (old name, pre-2026-07-27)**, rename it to `UaRO Patcher.app` per Step 11's current naming, updating `Info.plist` (`CFBundleName`/`CFBundleDisplayName`/`CFBundleIdentifier`/`CFBundleExecutable`) and the script filename (`uaro-launch` → `uaro-patcher`) to match, then re-sign and re-register — don't leave an install half-migrated with the old bundle name but new internal content.
- **If `/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher` exists**, also check whether it has Step 11's crash-dialog mitigation: `grep -q ShowCrashDialog "/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher"`. If it doesn't, tell the user: *"There's also a fix available that stops the known 'Program Error' popup from appearing at all — want me to update the launcher?"* Rebuild the script per Step 11's current version if they say yes.
- **If `/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher` exists but lacks the Launch Game handoff check** — `grep -q 'pgrep -f "uaRO.exe"' "/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher"` finds nothing — it has the known ghost-second-patcher bug (clicking the patcher's Launch Game button also spawns a second patcher window; see `TROUBLESHOOTING.md`). Tell the user and rebuild per Step 11's current version if they say yes, then re-sign.
- **If `/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings` exists**, verify that it contains the bundle-local runtime verifier and deterministic executor calls from Step 11 (`settings_runtime_verify.py`, `fcom apply`, and an independent `fcom check`). If any is absent, tell the user the launcher predates the deterministic Settings route and rebuild it from Step 11, then re-sign per the standing rule below.
- **If `/Applications/UaRO Game.app` is missing (install predates 2026-07-27)**, offer to add it per Step 11's current version: *"There's now a third launcher option, `UaRO Game`, that skips the patcher for a faster relaunch — it comes with a real trade-off (see Step 11/`TROUBLESHOOTING.md`) I want you to be aware of before I add it. Want me to build it?"* Only build it if the user says yes — don't add it silently, since accepting its risk is the user's call, not a default.
- **If `/opt/homebrew/bin/uaro-cli` is missing (install predates 2026-07-27)**, mention it's available and offer to add it per the *Optional: uaro-cli command-line helper* section below — this one carries no meaningful risk (it only wraps the kill/launch/repair operations this file already documents doing manually), so it's fine to build it as soon as the user says they'd find it useful, no special caution needed the way `UaRO Game.app` requires.
- **Whenever any launcher script gets edited here** (not just at first build) — re-run Step 11's `codesign --force --deep --sign -` on that bundle afterward, and check whether the same edit belongs in the other launchers too (see Step 11's standing rule on this) before moving on.

Tell the user plainly what was found (or that nothing was) before proceeding, and adjust the plan instead of blindly redoing finished work:

- **Whisky.app / CLI already present and working** → skip straight to checking the runtime (Step 4's verify command), don't reinstall.
- **A bottle already exists** (any name) → ask whether to reuse it or make a fresh one; if reusing, that bottle's real name becomes `BOTTLE_NAME` for every later step — never assume `uaro`.
- **An existing uaRO install is found** → ask the user whether this is a repair/reconfigure (skip Step 6-7, jump to verifying Steps 8-11 against the existing `$GAME_DIR`) or whether they want a clean second copy elsewhere.
- **Nothing found anywhere** → proceed with Steps 1-12 as a genuine fresh install.

## 2b. Kick off the uaRO installer download now — don't wait until Step 6

The installer sits behind a login wall (`https://uaro.net/cp/?module=account&action=login`) and is a multi-GB file — both mean this is slow and 100% human-driven, so start it now, in parallel with Steps 1–5, rather than discovering at Step 6 that nobody's downloaded anything yet:

> [!IMPORTANT]
> **Please go log in and start the download now:** open `https://uaro.net/cp/?module=account&action=login`, log in with your uaRO account, and start downloading the installer. **Don't have a uaRO account yet?** The same site has a registration/sign-up option — create one first, then come back to this login page. It's large, so let it run in the background — I'll get Homebrew/Whisky/the runtime set up in the meantime, and check back for it once both are ready.

This background download does **not** change the per-step approval gate in 1a — keep posting the progress table and stopping for explicit approval after every one of Steps 1–5, exactly as normal. The download simply runs unattended in another window while the user is replying between steps; it is not a license to chain Steps 1–5 together without waiting for approval.

Don't wait on the exact filename to identify it once it lands — **browsers frequently rename downloads** (`UaRO_Setup(1).zip`, a generic `download.zip`, etc.), but the installer's **file size stays constant** for a given build regardless of what it's named. Detect it by size instead:

```bash
# ~4.7GB observed on a previous run — use a wide margin since future uaRO
# builds may differ slightly. Widen further if this comes up empty.
find ~/Downloads ~/Desktop -maxdepth 1 -type f -size +4000M -size -6000M -exec ls -lh {} \; 2>/dev/null
```

If more than one file matches, ask the user which one; if none match yet, the download isn't done — check again later rather than guessing at a partial file.

**A file matching the size window isn't necessarily finished** — it could still be actively growing and just passing through that range on its way to a larger final size, or the browser could still be flushing the last bit to disk. Confirm the size is actually stable before treating it as done, the same "check, wait, recheck" idea used for the iCloud gotcha elsewhere in this skill:

```bash
CANDIDATE="<matched_file>"   # <matched_file> is a placeholder -- substitute the actual path printed by the
                             # find command above (e.g. /Users/you/Downloads/UaRO_Setup(1).zip), the same
                             # substitute-before-running rule as Section 0's placeholder note and the worked
                             # <UUID>/<GUID> examples in Steps 5 and 10 -- running this literally, unedited,
                             # makes stat fail with "No such file or directory"
SIZE1=$(stat -f%z "$CANDIDATE")
sleep 5
SIZE2=$(stat -f%z "$CANDIDATE")
if [[ "$SIZE1" != "$SIZE2" ]]; then
  echo "Still growing ($SIZE1 -> $SIZE2 bytes) — download still in progress, check again in a bit"
else
  echo "Size stable at $SIZE2 bytes — looks finished, safe to proceed"
fi
```

Once the size is confirmed stable, **relocate it immediately** rather than leaving it in `~/Downloads`/`~/Desktop` — this doubles as prevention for the iCloud-relocation gotcha, since it's now out of the risky folders before that 30-second window in Step 6 even matters:

```bash
mkdir -p ~/Games
mv "<matched_file>" ~/Games/UaRO_Setup.zip
```

Set `INSTALLER_SOURCE` to that exact path so Step 6 can branch on it correctly:

```bash
INSTALLER_SOURCE=~/Games/UaRO_Setup.zip
```

This exact value matches Step 6's *first* `if` branch (already staged, nothing to fetch) — not the `curl` branch (a URL) or the `cp` branch (some other already-downloaded local path elsewhere). If this step wasn't used — the user handed you a URL directly, or a `.zip` sitting somewhere other than `~/Games/UaRO_Setup.zip` — set `INSTALLER_SOURCE` to that value instead before Step 6 runs; it isn't optional, Step 6's `if`/`elif`/`else` reads it as a real shell variable, not a placeholder.

## Phase A — Environment prep (Steps 1–4)

Homebrew, Rosetta 2, Whisky.app, and the WhiskyWine runtime — the four things this install needs in place before there's anywhere to put a bottle or a game.

## Step 1 — Homebrew

**Before running this, give the user one line of why:** *"First up: Homebrew — the tool this whole setup runs through, including installing Whisky itself in a couple steps. Along the way, this will also install `git` and a small part of Xcode (just the Command Line Tools, not the full app) — that's normal plumbing this process needs, not something you need to know how to use."*

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
brew --version   # verify
```

**On a truly from-scratch Mac, that `eval` line is not optional.** The official installer does not add Homebrew to the *current* shell's `PATH` — it only prints instructions to add `brew shellenv` to a shell profile for *future* sessions. Skipping it means `brew --version` (and every later `brew` call this session) fails with "command not found" even though Step 1 actually succeeded — don't misread that as an install failure.

**Tell the user before running this:** the installer may prompt for the Mac's admin/login password (it needs it the first time to create `/opt/homebrew`). That's expected — not a sign of anything wrong. If the command instead hangs or fails with something like `sudo: a password is required` rather than actually showing a password prompt, the current shell has no interactive terminal attached to answer it — ask the user to open a normal Terminal window and run the install command there directly.

**A second, unrelated popup can also appear here: macOS's own "Install Command Line Developer Tools" dialog.** This comes from `git`/`cc`, which Homebrew depends on underneath — not from the command above directly — and it only shows up on a Mac that's never had any developer tools installed before, which is common on a genuinely fresh machine. It's expected, not a sign of anything wrong. Tell the user plainly, before they see it and wonder what "Xcode" or "Command Line Tools" even are: *"You might see a system popup asking to install Command Line Developer Tools — that's normal, it's a small Apple toolkit Homebrew needs (it includes `git`). Click Install and wait; it can take a few minutes. Let me know once it's done and we'll continue."* If the user dismisses it instead of installing, later `git`-dependent steps can fail in confusing ways rather than at this step — `xcode-select -p` (prints a path like `/Library/Developer/CommandLineTools` if present, errors if not) is the quick way to check whether it actually finished.

## Step 2 — Rosetta 2 (Apple Silicon only)

```bash
if [[ "$(uname -m)" == "arm64" ]] && ! pgrep -q oahd; then
  softwareupdate --install-rosetta --agree-to-license
fi
pgrep -q oahd && echo "Rosetta OK"
```

This can also prompt for the Mac's admin/login password on some machines — same guidance as Step 1: expected if it happens, and if it hangs/fails instead of prompting, have the user run it themselves in a normal Terminal window.

## Step 3 — Whisky.app

**Check first — don't install unconditionally.** `2a` may already have flagged Whisky as present, but treat this as the actual gate rather than something to remember from a few steps back — running `brew install --cask whisky` against an already-installed, non-Homebrew-managed `Whisky.app` throws AppleEvents "not permitted" errors while brew tries to reconcile it, a noisy failure for what should be a no-op:

```bash
ls -d /Applications/Whisky.app ~/Applications/Whisky.app 2>/dev/null
command -v whisky
```

If either printed something, Whisky's already installed — skip straight to "Locate the CLI" below, don't run the install commands.

If nothing printed, try Homebrew — **do not skip this attempt on the assumption the cask is disabled.** Verify the result yourself rather than trusting the exit code alone, since a disabled/no-op cask can still exit 0 while installing nothing.

```bash
brew install --cask whisky
ls -d /Applications/Whisky.app ~/Applications/Whisky.app 2>/dev/null
```

If neither path exists after that, fall back to the GitHub release:

```bash
WHISKY_SOURCE="https://github.com/IsaacMarovitz/Whisky/releases/download/v2.3.5/Whisky.zip"
curl -fL --progress-bar -o /tmp/Whisky.zip "$WHISKY_SOURCE"
python3 scripts/whisky.py verify-download --file /tmp/Whisky.zip --source "$WHISKY_SOURCE"
ditto -xk /tmp/Whisky.zip /tmp/Whisky-extract
cp -R /tmp/Whisky-extract/Whisky.app /Applications/
xattr -dr com.apple.quarantine /Applications/Whisky.app 2>/dev/null || true
```

**If that download itself fails** (Whisky is unmaintained upstream, so a vanished tag/asset is possible): fall back to this repo's archived copy. The fallback is accepted only when its bytes match the same fixed release digest; its source provenance remains explicitly unconfirmed. This repo is public, so plain `curl` works with no auth needed:

```bash
WHISKY_SOURCE="https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/Whisky-app-2.3.5.zip"
curl -fL --progress-bar -o /tmp/Whisky.zip "$WHISKY_SOURCE"
python3 scripts/whisky.py verify-download --file /tmp/Whisky.zip --source "$WHISKY_SOURCE"
ditto -xk /tmp/Whisky.zip /tmp/Whisky-extract
cp -R /tmp/Whisky-extract/Whisky.app /Applications/
xattr -dr com.apple.quarantine /Applications/Whisky.app 2>/dev/null || true
```

Locate the CLI (brew symlink first, then inside whichever Whisky.app was found):

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
"$WHISKY" list   # should run without error, even with an empty bottle list
```

## Step 4 — WhiskyWine runtime (Wine 7.x + Apple GPTK + DXVK)

**Check first — don't re-download onto a runtime that's already working.** A previous run, or a bottle/runtime carried over from an earlier attempt, may already have this in place:

```bash
SUPPORT="$HOME/Library/Application Support/com.isaacmarovitz.Whisky"
plutil -extract version.major xml1 -o - "$SUPPORT/Libraries/WhiskyWineVersion.plist" 2>/dev/null \
  && "$SUPPORT/Libraries/Wine/bin/wine64" --version 2>/dev/null
```

If that printed both a version number and something like `wine-7.7`, the runtime's already installed and working — skip straight to Step 5, don't re-download.

If either came back empty, fetch it. Whisky's own downloader points at `data.getwhisky.app`, which is dead (confirm: `curl -I https://data.getwhisky.app/Libraries.zip` → 404) — never rely on Whisky's own "Install GPTK" button either, it shows a fake instant success and leaves an empty folder. The Internet Archive snapshot once documented here as the fallback is now unreliable itself — three consecutive live attempts hung/failed to connect rather than returning even an error — so **go straight to this repo's own archived copy** (byte-identical, confirmed reachable, no auth needed since this repo is public):

```bash
mkdir -p ~/Downloads   # transient scratch only — the .zip itself isn't at risk the way an extracted app bundle is, but move fast
caffeinate -i curl -fL --progress-bar --max-time 300 -o ~/Downloads/WhiskyWine-Libraries.zip \
  https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/WhiskyWine-Libraries-2.5.0.zip
```

**`caffeinate -i` wraps this download** — unlike a browser download (which requests its own "stay awake" assertion automatically), a `curl` call run this way has no such protection. On a laptop that's idle-timeout-eligible, this download can take a few minutes; without `caffeinate`, the Mac going to sleep partway through would stall or corrupt it, and it isn't obvious to a user why. `caffeinate` here just holds the system awake for exactly as long as `curl` is running, then releases automatically.

**If this repo's own release is ever unreachable too** (GitHub outage, etc.), the Internet Archive snapshot is a last-resort second fallback — same URL as before this version, now with a short timeout so a dead endpoint fails fast instead of hanging:

```bash
caffeinate -i curl -fL --progress-bar --max-time 30 -o ~/Downloads/WhiskyWine-Libraries.zip \
  "https://web.archive.org/web/20240416174812id_/https://data.getwhisky.app/Libraries.zip"
```

Either way, continue identically from here:

```bash
cd ~/Downloads
ditto -xk WhiskyWine-Libraries.zip .
mkdir -p "$SUPPORT"
tar -xzf Libraries.tar.gz -C "$SUPPORT"
```

**Quarantine-clear, defensively.** Files extracted by `tar` come out read-only, and macOS's `xattr -d` requires write permission on the target just to *attempt* a delete — so it errors on nearly every file, even though (confirmed) these files never had `com.apple.quarantine` set in the first place (only the harmless `com.apple.provenance`, which doesn't block execution). This is a no-op either way, but do it defensively so it can never abort a `set -e` script:

```bash
chmod -R u+w "$SUPPORT/Libraries" 2>/dev/null || true
xattr -dr com.apple.quarantine "$SUPPORT/Libraries" 2>/dev/null || true
```

**Stamp the runtime version file — write this exact structured plist.** Whisky decides "is WhiskyWine installed" purely by whether `Libraries/WhiskyWineVersion.plist` decodes into its `WhiskyWineVersion { version: SemanticVersion }` Codable struct (confirmed directly against `Whisky-App/Whisky`'s `WhiskyWineInstaller.swift` and `SwiftPackageIndex/SemanticVersion`'s Codable extension — Whisky never installs a custom decoding strategy, so the default structured-dict shape applies, and *all five keys are required*, nested one level under `version`). A plain string value like `"2.5.0"` throws a `typeMismatch` and silently fails this check.

```bash
cat > "$SUPPORT/Libraries/WhiskyWineVersion.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>version</key>
	<dict>
		<key>major</key>
		<integer>2</integer>
		<key>minor</key>
		<integer>5</integer>
		<key>patch</key>
		<integer>0</integer>
		<key>preRelease</key>
		<string></string>
		<key>build</key>
		<string></string>
	</dict>
</dict>
</plist>
PLIST
```

(Note the exact version number written here is functionally irrelevant — Whisky's remote-update check hits the same dead endpoint and always fails closed, so it never prompts a re-download regardless. Only the *schema* above matters.)

**MANDATORY verification — `plutil -lint` is not enough**, it only proves the XML parses, not that Whisky can decode it into the type it expects:

```bash
plutil -lint "$SUPPORT/Libraries/WhiskyWineVersion.plist"
for k in major minor patch preRelease build; do
  plutil -extract "version.$k" xml1 -o - "$SUPPORT/Libraries/WhiskyWineVersion.plist" \
    || echo "MISSING KEY: $k — fix before continuing"
done
"$SUPPORT/Libraries/Wine/bin/wine64" --version   # should print something like wine-7.7
```

## Phase B — Bottle & game install (Steps 5–8)

Create the bottle, get uaRO's own installer downloaded and run inside it, then patch the one binary that crashes under Rosetta.

## Step 5 — Create & configure the bottle

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
"$WHISKY" create "$BOTTLE_NAME"   # e.g. uaro
"$WHISKY" list                    # find the bottle, note its UUID (the *printed path* is cosmetically
                                   # wrong — it may show ~/Library/Containers/Whisky/... which doesn't
                                   # exist; the real path is always:
                                   # ~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/<UUID>)

# This is the first real test of Section 0's placeholder-substitution rule: read the
# UUID `whisky list` just printed (e.g. `4F2A1B3C-5D6E-7F80-9A1B-2C3D4E5F6A7B`), then
# write that literal string in place of <UUID> below -- e.g.
#   META="$HOME/Library/.../Bottles/4F2A1B3C-5D6E-7F80-9A1B-2C3D4E5F6A7B/Metadata.plist"
# not the placeholder text as shown.
META="$HOME/Library/Containers/com.isaacmarovitz.Whisky/Bottles/<UUID>/Metadata.plist"   # substitute the real UUID
plutil -replace dxvkConfig.dxvk           -bool true                                  "$META"
plutil -replace dxvkConfig.dxvkAsync      -bool true                                  "$META"
plutil -replace wineConfig.windowsVersion -string "win10"                             "$META"
plutil -replace wineConfig.enhancedSync   -xml '<dict><key>msync</key><dict/></dict>' "$META"
plutil -replace wineConfig.avxEnabled     -bool true                                  "$META"
plutil -lint "$META" && plutil -p "$META"
```

All five calls are safe to run unconditionally — they're idempotent, even though a fresh bottle typically already defaults `dxvkAsync`, `windowsVersion`, and `enhancedSync` correctly and only `dxvk`/`avxEnabled` actually need flipping. Confirm the printed result shows all five as intended before moving on.

**Runtime route gate — keep alternate backend experiments separate from the default install.** This skill's supported default route is the DXVK configuration above. If an external guide proposes builtin `wined3d`, a different `d3d9` policy, a different sync mode, or another `WINEDLLOVERRIDES` value, treat that as an isolated diagnostic branch rather than silently replacing the default. Before testing the branch, record the current `Metadata.plist`, the exact launcher environment, and one reproducible baseline symptom. Test the same target, execution, and behavior gates again; a launcher that opens is not enough. If the branch does not improve the same symptom under the same workload, restore the recorded default configuration and keep the alternative documented as unconfirmed.

**Self-healing check — confirm `wine64` is actually reachable through this bottle before trusting it, don't wait until Step 7's crash to find out:**

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
command -v wine64 || echo "MISSING"
```

If that prints `MISSING` on a machine where Step 4 otherwise looked fine, the runtime and the bottle's environment aren't actually linked (seen on real machines where WhiskyWine was present on disk but a stale/mismatched `shellenv` path pointed elsewhere). Fix by re-running Step 4's install/verify, then re-check this before proceeding — don't proceed into Step 6/7 on a bottle where this printed `MISSING`.

## Step 6 — Download & extract the uaRO installer

`INSTALLER_SOURCE` resolves to either a URL or an already-downloaded local `.zip` path — branch on which one it actually is, don't hand a local path straight to `curl` (it doesn't reliably fetch bare local paths the way `cp` does). If 2b already relocated the download to `~/Games/UaRO_Setup.zip`, there's nothing to fetch — skip straight to extraction. **`$INSTALLER_SOURCE` must actually be set as a shell variable before the `if` below runs** — it's resolved, not a placeholder, so set it explicitly if this is a fresh shell invocation (same re-derivation rule as `$BOTTLE_NAME`/`$GAME_DIR`/`$WHISKY` — see the callout after the Parameters table):

```bash
INSTALLER_SOURCE=~/Games/UaRO_Setup.zip   # if 2b staged it; otherwise the URL or local path the user actually gave you
mkdir -p "$(dirname "$GAME_DIR")"   # e.g. ~/Games
if [[ "$INSTALLER_SOURCE" == ~/Games/UaRO_Setup.zip ]]; then
  : # already staged by 2b — nothing to do
elif [[ "$INSTALLER_SOURCE" =~ ^https?:// ]]; then
  caffeinate -i curl -fL --progress-bar -o ~/Games/UaRO_Setup.zip "$INSTALLER_SOURCE"
else
  cp "$INSTALLER_SOURCE" ~/Games/UaRO_Setup.zip
fi
mkdir -p ~/Games/UaRO_Setup
ditto -xk ~/Games/UaRO_Setup.zip ~/Games/UaRO_Setup   # NEVER unzip — macOS's bundled Info-Zip
                                                       # silently no-ops on ZIP64 archives over 4GB
                                                       # (this installer is ~4.7GB): empty folder, no error.
```

**`caffeinate -i` on the `curl` branch above, same reason as Step 4's download and Step 7's install** — this is the same ~4.7GB installer (per 2b's own size-window comment), fetched directly rather than staged via a browser, so it has no "stay awake" assertion of its own; an idle-timeout sleep mid-download would stall or corrupt it with no clear error pointing at why.

**MANDATORY iCloud-safety check — do this even if the pre-flight iCloud probe came back negative:**

```bash
sleep 30
test -f ~/Games/UaRO_Setup/UaRO_Setup.exe && echo "Still here — safe to proceed" \
  || { echo "GONE — check for it under ~/Library/Mobile Documents/com~apple~CloudDocs/... (mdfind -name UaRO_Setup.exe), then move GAME_DIR/scratch dir somewhere else entirely and redo this step"; exit 1; }
```

This is not paranoia — on a real run, files extracted to `~/Downloads` passed an immediate check, then vanished from that path within under a minute (relocated into iCloud's mirror by the OS), breaking the in-progress install with a `c0000135` file-not-found error from Wine. `~/Games` and `~/Library/Application Support/...` were both confirmed to survive a 30-second wait; `~/Desktop`, `~/Documents`, and `~/Downloads` are all suspect regardless of which specific iCloud toggle is/isn't enabled.

## Step 7 — Run the installer

**As soon as Step 6 finishes — before running anything below — post this to the user verbatim.** The installer is a normal interactive GUI wizard; whether the user is clicking through it themselves or you're driving it via computer-use tools, these 4 screens are the only ones that matter, and getting any of them wrong means redoing Steps 6–7:

> [!IMPORTANT]
> **The installer is about to open. Here's exactly what to do on each screen — nothing else needs to change:**
>
> | # | Screen | Do this |
> |---|---|---|
> | 1 | **Select Setup Install Mode** | Click the **first option** ("Install for me only" / current user) — ⚠️ **not** "Install for all users" |
> | 2 | **Select Destination Location** | ✅ Leave the path exactly as shown — **do not** change or browse to a different folder |
> | 3 | **Installing** | Just wait — this is a multi-GB install, it can take a while, don't close the window |
> | 4 | **Completing the Setup Wizard** | ⚠️ **Uncheck "Launch \<game\>"** before clicking Finish — the game is not configured yet (Steps 8–11 still need to run first); launching now would run an unpatched, unconfigured copy |

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
# Note: this sed doubles each backslash (\\ per separator, not a single \) --
# looks odd but is intentional/verified-safe: Windows path parsing collapses
# redundant separators, and this exact form was confirmed working end-to-end
# on a real install (Step 7's own landed-where-asked check afterward is the
# actual safety net regardless).
WIN_DEST="Z:$(printf '%s' "$GAME_DIR" | sed 's:/:\\\\:g')"
nohup caffeinate -i wine64 ~/Games/UaRO_Setup/UaRO_Setup.exe "/DIR=$WIN_DEST" >/tmp/uaro_installer.log 2>&1 &
disown
```

**`caffeinate -i` is there for the same reason as Step 4's download** — Screen 3 ("Installing") can run for several minutes with the user just watching, and neither Wine nor Inno Setup requests a "stay awake" assertion on their own. If the Mac idles into sleep mid-install, the install stalls without any clear error pointing at why. `caffeinate` holds the assertion only as long as `wine64` is running and releases it automatically once the wizard's process exits.

**Launch this in the background — never run it as a single blocking foreground call.** This is a GUI wizard a human has to click through, and Screen 3 ("Installing," a multi-GB unpack) can genuinely take many minutes. If you instead run `wine64 ...` synchronously and wait for it to exit, your own command-execution tooling will very likely time out while the wizard is still legitimately open on screen and waiting for a click — that reads as a crash, but isn't one. Background it (`&`/`nohup` as above, or your tool's own non-blocking/background-execution mode if it has one), tell the user you'll check back, then confirm completion with a separate, short follow-up check rather than one long blocking wait — the same `$GAME_DIR`/`uaRO.exe` check just below doubles as that completion signal, not just a post-hoc verification.

**Tell the user this opens a real window that may not automatically pop to the front** — nothing in the terminal will look like it's "doing" anything once this command starts. Have them check the Dock (or press Cmd+Tab) for the installer window if it doesn't appear immediately, rather than assuming it silently failed.

Use `wine64` directly — never `whisky run` (that goes through `WhiskyCmd`, which is App-sandboxed, so Inno Setup can only write inside the Whisky container regardless of what `/DIR=` says). Confirm afterward that `$GAME_DIR` now actually contains the extracted game files before moving to Step 8.

**Verify it actually landed where asked — some Inno Setup installer builds silently ignore `/DIR=`:**

```bash
ls "$GAME_DIR"/uaRO.exe 2>/dev/null && echo "Landed at \$GAME_DIR — OK" || {
  echo "Not at \$GAME_DIR — searching bottle drive_c for where it actually went..."
  find ~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/*/drive_c -maxdepth 4 -iname "uaRO.exe" 2>/dev/null
}
```

If it landed somewhere else, **adopt that real path as `GAME_DIR` for every step from here on** rather than fighting the installer — don't assume the value you passed to `/DIR=` is where it ended up.

## Step 8 — Patch setup.exe (FCOM byte-patches, two sites)

setup.exe here is a different file from UaRO_Setup.exe, the installer Step 6/7 just downloaded and ran, despite the near-identical name. UaRO_Setup.exe is the Inno Setup installer, already done with its job by this point. setup.exe is RO OpenSetup, the game's own graphics-config tool, sitting inside GAME_DIR (installed alongside the game itself, not related to Step 6/7's installer). This step inspects that second file, not the first.

Rosetta cannot translate certain alternate x87 FCOM instruction encodings; running them crashes setup.exe with an illegal-instruction error. Read-only classification is now provided by the deterministic executor. This section keeps the policy and interpretation; the byte-reading algorithm lives in `scripts/uaro.py`.

Known states:

- Site A at 0x2C0CD: unpatched `dc`; patched `d8`.
- Site B at 0x21E39: unpatched `dcd8dfe0`; patched `ddd8b440`.

The expected pair is classified only after both sites are read. `UNKNOWN`, `MIXED`, and `TRUNCATED` are fail-closed states. A read-only check never creates a backup and never writes `setup.exe`.

### Shared deterministic read-only executor routing

The read-only FCOM and structural-inspection blocks below must be run in the same shell invocation as this helper block so the functions are available. Set `AURO_REPO_ROOT` to this checkout when the current working directory is elsewhere; when it is unset, the current directory is used only if Git can resolve it to the expected repository. The helper validates the Git root, the expected `origin`, and the readable executor file. A missing or different origin is `BLOCKED`; never guess another checkout. No private absolute path is embedded.

```bash
resolve_uaro_executor() {
  local repo_hint="${AURO_REPO_ROOT:-$PWD}"
  [[ -n "$repo_hint" ]] || {
    echo "BLOCKED: AURO_REPO_ROOT/PWD is empty; cannot resolve the deterministic executor" >&2
    return 1
  }
  local repo_root
  repo_root="$(git -C "$repo_hint" rev-parse --show-toplevel 2>/dev/null)" || {
    echo "BLOCKED: cannot resolve a Git repository root from AURO_REPO_ROOT/PWD" >&2
    return 1
  }
  local origin_url
  origin_url="$(git -C "$repo_root" config --get remote.origin.url 2>/dev/null || true)"
  case "$origin_url" in
    https://github.com/jirukouya/auRO-whisky-macOS-setup|https://github.com/jirukouya/auRO-whisky-macOS-setup.git|git@github.com:jirukouya/auRO-whisky-macOS-setup.git|ssh://git@github.com/jirukouya/auRO-whisky-macOS-setup.git)
      ;;
    *)
      echo "BLOCKED: Git repository origin is not the expected auRO-whisky-macOS-setup checkout" >&2
      return 1
      ;;
  esac
  local executor="$repo_root/scripts/uaro.py"
  [[ -f "$executor" && -r "$executor" ]] || {
    echo "BLOCKED: deterministic executor is missing or unreadable: $executor" >&2
    return 1
  }
  printf '%s\n' "$executor"
}

validate_uaro_json() {
  local payload="$1"
  local expected_operation="$2"
  local expected_path_key="$3"
  local expected_path="$4"
  local expected_capability="${5:-}"
  local validation_mode="${6:-readonly}"
  python3 - "$payload" "$expected_operation" "$expected_path_key" "$expected_path" "$expected_capability" "$validation_mode" <<'PYEOF'
import json
import os
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed deterministic executor JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(payload, dict):
    print("BLOCKED: deterministic executor JSON is not an object", file=sys.stderr)
    raise SystemExit(1)
expected_operation = sys.argv[2]
expected_path_key = sys.argv[3]
expected_path = sys.argv[4]
expected_capability = sys.argv[5]
validation_mode = sys.argv[6]
missing = [key for key in ("operation", "capability", "result", "mutation") if key not in payload]
if missing:
    print(f"BLOCKED: deterministic executor JSON is incomplete: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
if payload["operation"] != expected_operation:
    print("BLOCKED: deterministic executor returned an unexpected operation", file=sys.stderr)
    raise SystemExit(1)
if payload["result"] != "success":
    print("BLOCKED: deterministic executor did not report success", file=sys.stderr)
    raise SystemExit(1)
if validation_mode == "readonly" and payload["mutation"] is not False:
    print("BLOCKED: read-only executor result did not prove mutation=false", file=sys.stderr)
    raise SystemExit(1)
if validation_mode == "apply" and not isinstance(payload["mutation"], bool):
    print("BLOCKED: mutation executor result did not provide a boolean mutation field", file=sys.stderr)
    raise SystemExit(1)
if expected_capability and payload.get("capability") != expected_capability:
    print("BLOCKED: deterministic executor returned an unexpected capability", file=sys.stderr)
    raise SystemExit(1)
if expected_path_key:
    reported_path = payload.get(expected_path_key)
    if not isinstance(reported_path, str):
        print("BLOCKED: deterministic executor result omitted the expected target path", file=sys.stderr)
        raise SystemExit(1)
    reported_real = os.path.realpath(os.path.abspath(reported_path))
    expected_real = os.path.realpath(os.path.abspath(expected_path))
    if reported_real != expected_real:
        print("BLOCKED: deterministic executor result names a different target", file=sys.stderr)
        raise SystemExit(1)
print(json.dumps(payload, sort_keys=True))
PYEOF
}
```

### Read-only FCOM classification

Run the helper block and this block together. `UNPATCHED` is valid evidence that a later, separately authorized mutation could be considered; it is not mutation authority. `PATCHED` means no mutation is needed. Every other state blocks.

```bash
SETUP="${GAME_DIR:?Resolve GAME_DIR to the installed game directory before running this block}/setup.exe"
AURO_EXECUTOR="$(resolve_uaro_executor)" || { echo "BLOCKED: deterministic executor path is unavailable" >&2; exit 1; }

if ! CHECK_JSON="$(python3 "$AURO_EXECUTOR" fcom check "$SETUP")"; then
  echo "BLOCKED: deterministic FCOM check failed" >&2
  exit 1
fi
if ! CHECK_JSON="$(validate_uaro_json "$CHECK_JSON" "fcom-check" "target" "$SETUP" "READ" "readonly")"; then
  exit 1
fi
if ! CHECK_STATE="$(python3 - "$CHECK_JSON" <<'PYEOF'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed FCOM evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
required = ("state", "site_a", "site_b", "backup_created", "verification")
missing = [key for key in required if key not in payload]
if missing:
    print(f"BLOCKED: incomplete FCOM evidence: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] not in ("UNPATCHED", "PATCHED", "MIXED", "UNKNOWN", "TRUNCATED"):
    print("BLOCKED: unexpected FCOM state", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] == "UNPATCHED" and (payload["site_a"] != "unpatched" or payload["site_b"] != "unpatched"):
    print("BLOCKED: FCOM check state and site evidence disagree", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] == "PATCHED" and (payload["site_a"] != "patched" or payload["site_b"] != "patched"):
    print("BLOCKED: FCOM check state and site evidence disagree", file=sys.stderr)
    raise SystemExit(1)
if payload["backup_created"] is not False or payload["verification"] != "not-run":
    print("BLOCKED: read-only FCOM evidence contains mutation or backup claims", file=sys.stderr)
    raise SystemExit(1)
print(payload["state"])
PYEOF
)"; then
  exit 1
fi

case "$CHECK_STATE" in
  UNPATCHED)
    echo "TARGET FCOM evidence: UNPATCHED; mutation authority remains denied"
    ;;
  PATCHED)
    echo "TARGET FCOM evidence: PATCHED; no mutation needed"
    ;;
  MIXED|UNKNOWN|TRUNCATED)
    echo "BLOCKED: FCOM state=$CHECK_STATE; no write or backup is authorized" >&2
    exit 1
    ;;
  *)
    echo "BLOCKED: unexpected FCOM state=$CHECK_STATE" >&2
    exit 1
    ;;
esac
```

If the executor is missing, cannot be resolved, exits nonzero, returns malformed or incomplete JSON, or names a different target, stop. Do not fall back to a shell byte classifier. The executor's structured result is evidence only; it does not prove process execution, launcher behavior, patch freshness, or user authority.

### Deterministic FCOM mutation

For a fresh or adopted install, run this block after the read-only check above in the same shell invocation and only after the existing Step 8 approval/authority decision for that install route. The initial `UNPATCHED` result is evidence that mutation may be needed; it is not mutation authority. This existing Step 8 authority gate permits the deterministic executor to perform the one active mutation transaction. `fcom apply` owns backup creation, target identity checks, exact writes, and verification. If it fails, block; do not fall back to an inline shell patch or the later Settings launcher.

```bash
if [[ "$CHECK_STATE" == "PATCHED" ]]; then
  echo "TARGET FCOM evidence: PATCHED; no mutation needed"
elif [[ "$CHECK_STATE" == "UNPATCHED" ]]; then
  if ! APPLY_JSON="$(python3 "$AURO_EXECUTOR" fcom apply "$SETUP")"; then
    echo "BLOCKED: deterministic FCOM apply failed" >&2
    exit 1
  fi
  if ! APPLY_JSON="$(validate_uaro_json "$APPLY_JSON" "fcom-apply" "target" "$SETUP" "REVERSIBLE_MUTATION" "apply")"; then
    exit 1
  fi
  if ! APPLY_STATE="$(python3 - "$APPLY_JSON" <<'PYEOF'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed FCOM apply evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
required = (
    "operation", "capability", "state", "pre_state", "post_state",
    "site_a", "site_b", "backup_created", "mutation", "verification", "reason",
)
missing = [key for key in required if key not in payload]
if missing:
    print(f"BLOCKED: incomplete FCOM apply evidence: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
if payload["post_state"] != "PATCHED" or payload["state"] != payload["pre_state"]:
    print("BLOCKED: FCOM apply did not prove a coherent PATCHED result", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] not in ("UNPATCHED", "PATCHED"):
    print("BLOCKED: FCOM apply reported an invalid pre-state", file=sys.stderr)
    raise SystemExit(1)
if payload["verification"] != "passed":
    print("BLOCKED: FCOM apply verification did not pass", file=sys.stderr)
    raise SystemExit(1)
if payload["reason"] not in ("patched and verified", "already patched; no-op"):
    print("BLOCKED: FCOM apply returned an unrecognized success reason", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] == "UNPATCHED" and payload["mutation"] is not True:
    print("BLOCKED: FCOM apply reported UNPATCHED without a completed mutation", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] == "PATCHED" and (payload["mutation"] is not False or payload["backup_created"] is not False):
    print("BLOCKED: FCOM no-op result claimed mutation or backup creation", file=sys.stderr)
    raise SystemExit(1)
print("PATCHED")
PYEOF
)"; then
    exit 1
  fi

  if ! POST_CHECK_JSON="$(python3 "$AURO_EXECUTOR" fcom check "$SETUP")"; then
    echo "BLOCKED: independent post-apply FCOM check failed" >&2
    exit 1
  fi
  if ! POST_CHECK_JSON="$(validate_uaro_json "$POST_CHECK_JSON" "fcom-check" "target" "$SETUP" "READ" "readonly")"; then
    exit 1
  fi
  if ! python3 - "$POST_CHECK_JSON" <<'PYEOF'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed post-apply FCOM evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
required = ("state", "site_a", "site_b", "backup_created", "verification", "mutation", "capability")
missing = [key for key in required if key not in payload]
if missing:
    print(f"BLOCKED: incomplete post-apply FCOM evidence: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] != "PATCHED" or payload["site_a"] != "patched" or payload["site_b"] != "patched":
    print("BLOCKED: independent post-apply FCOM check did not prove both sites PATCHED", file=sys.stderr)
    raise SystemExit(1)
if payload["mutation"] is not False or payload["backup_created"] is not False or payload["verification"] != "not-run":
    print("BLOCKED: independent post-apply FCOM check was not read-only", file=sys.stderr)
    raise SystemExit(1)
print("PATCHED")
PYEOF
  then
    exit 1
  fi
  echo "FCOM apply succeeded and independent PATCHED check passed"
else
  echo "BLOCKED: FCOM state=$CHECK_STATE; no mutation is authorized" >&2
  exit 1
fi
```

A failed deterministic apply is a blocked transaction. Rollback is performed by reverting the Stage 2.1 integration commit, never by executing a legacy mutation fallback.

### Explicit structural target inspection

Use this route for target evidence only. It checks the explicitly supplied game and application paths and reports `EXECUTION=UNCONFIRMED` and `BEHAVIOR=UNCONFIRMED` even when all structural facts are present. `UaRO Patcher.app` and `UaRO Settings.app` are required structural targets; `UaRO Game.app` remains optional.

Run the helper block and this block together. `APPS_DIR` defaults to `/Applications` and may be set to another explicitly inspected application directory for a controlled verification.

```bash
GAME_DIR="${GAME_DIR:?Resolve GAME_DIR to the installed game directory before running this block}"
APPS_DIR="${APPS_DIR:-/Applications}"
AURO_EXECUTOR="$(resolve_uaro_executor)" || { echo "BLOCKED: deterministic executor path is unavailable" >&2; exit 1; }

if ! INSPECT_JSON="$(python3 "$AURO_EXECUTOR" inspect --game-dir "$GAME_DIR" --apps-dir "$APPS_DIR")"; then
  echo "BLOCKED: deterministic structural inspection failed" >&2
  exit 1
fi
if ! INSPECT_JSON="$(validate_uaro_json "$INSPECT_JSON" "inspect" "game_dir" "$GAME_DIR" "READ" "readonly")"; then
  exit 1
fi
python3 - "$INSPECT_JSON" <<'PYEOF'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed structural evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
if payload.get("evidence_scope") != "explicit structural facts only":
    print("BLOCKED: structural inspection scope is not explicit", file=sys.stderr)
    raise SystemExit(1)
if payload.get("execution") != "UNCONFIRMED":
    print("BLOCKED: structural inspection cannot prove execution", file=sys.stderr)
    raise SystemExit(1)
if payload.get("mutation") is not False or payload.get("deletion_authority") is not False:
    print("BLOCKED: structural inspection returned an authority claim", file=sys.stderr)
    raise SystemExit(1)
evidence = payload.get("evidence")
if not isinstance(evidence, dict):
    print("BLOCKED: structural inspection omitted evidence", file=sys.stderr)
    raise SystemExit(1)
for key in ("game_dir_exists", "uaro_exe_exists", "setup_exe_exists", "fcom", "savedata"):
    if key not in evidence:
        print(f"BLOCKED: structural inspection omitted {key}", file=sys.stderr)
        raise SystemExit(1)
if not all(evidence[key] is True for key in ("game_dir_exists", "uaro_exe_exists", "setup_exe_exists")):
    print("BLOCKED: required game target structure is missing", file=sys.stderr)
    raise SystemExit(1)
fcom = evidence["fcom"]
if not isinstance(fcom, dict) or fcom.get("result") != "success" or fcom.get("state") not in ("UNPATCHED", "PATCHED"):
    print("BLOCKED: FCOM structural evidence is unavailable or fail-closed", file=sys.stderr)
    raise SystemExit(1)
apps = payload.get("apps")
if not isinstance(apps, dict):
    print("BLOCKED: application structural evidence is missing", file=sys.stderr)
    raise SystemExit(1)
for name in ("UaRO Patcher.app", "UaRO Settings.app"):
    record = apps.get(name)
    if not isinstance(record, dict) or record.get("required") is not True or record.get("exists") is not True:
        print(f"BLOCKED: required launcher structure is missing: {name}", file=sys.stderr)
        raise SystemExit(1)
optional_game = apps.get("UaRO Game.app")
if not isinstance(optional_game, dict) or optional_game.get("required") is not False:
    print("BLOCKED: optional Game.app was not represented as optional", file=sys.stderr)
    raise SystemExit(1)
print("TARGET=PASS (explicit structural evidence only)")
print("EXECUTION=UNCONFIRMED; BEHAVIOR=UNCONFIRMED")
PYEOF
```

A missing or unreadable target, missing required launcher structure, unavailable FCOM evidence, malformed result, nonzero executor exit, or unresolved invocation path is `BLOCKED`. Structural evidence does not prove Whisky/Wine runtime use, process arguments, launcher behavior, login stability, patch freshness, overall install health, or user authority. Any later mutation, backup, uninstall, or deletion route remains separately gated and is not part of this read-only integration.

If setup.exe crashes at a different 0042xxxx address, subtract the PE ImageBase 0x400000 to get the file offset. 0x0042C0CD maps to Site A and 0x00421E39 maps to Site B. Any other address is an uncatalogued third site from a newer installer build; dump the surrounding bytes and stop rather than changing these approved historical values.

## Phase C — Client readiness (Steps 9–9b–10)

Get the patcher's embedded browser working (Gecko), fix the one keybind scheme that's wrong by default, then write the game's own config files.

## Step 9 — Pre-install Wine Gecko (mandatory, before `UaRO Patcher.app` is ever launched)

Do this right after Step 8, before the patcher is run for the first time. **This is a hard functional dependency, not a cosmetic prompt.** `UaRo Patcher.exe`'s initial patch-check runs through an embedded HTML/browser control — without Gecko it sits stuck at "Getting patch_main.txt..." forever, with a blank white panel and a progress bar that never moves.

**Note the casing: `UaRo Patcher.exe` (lowercase "o") is the game's actual on-disk filename, used consistently throughout this file wherever the raw `.exe` inside `$GAME_DIR` is meant — not a typo.** It's different from `UaRO Patcher.app` (capital "O"), the launcher bundle Step 11 builds in `/Applications` that runs this `.exe`, and from `uaRO.exe`/`UaRO_Setup.exe` (the game client and the installer, both separate files). All four names are real and intentional; none are interchangeable.

There's a second, more important reason to do this ahead of time: the native "Wine Gecko Installer" dialog (source: `dl.winehq.org` — legitimate and currently working, unrelated to the dead `data.getwhisky.app` endpoint used elsewhere in this process) appears to show only **once**. Clicking **Cancel** instead of **Install** seems to make Wine remember that decision and never show the prompt again — leaving the patcher permanently stuck with no further recovery path short of manually re-triggering a Gecko install. Pre-installing removes this one-way door entirely.

**Check first — don't assume this bottle needs it.** A bottle carried over from a previous install or attempt may already have Gecko installed:

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
grep -qi '^gecko' "$WINEPREFIX/winetricks.log" 2>/dev/null && echo "Gecko already installed in this bottle"
```

If that printed the "already installed" line, skip straight to the MANDATORY verification below — don't re-run `winetricks -q gecko`. And either way, once you do run it: **a quiet `winetricks -q gecko` that prints nothing unusual and shows no dialog is the *expected* result when Gecko's already present, not a sign anything went wrong** — winetricks no-ops silently in that case. Don't read silence as failure, and don't confuse it with the separate, already-known post-Gecko patcher crash (see the note right after the verification step below).

**Primary method — non-interactive:**

```bash
brew install winetricks   # if not already present
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
env | grep -i '^WINE'     # confirm WINEPREFIX actually points at the right bottle before proceeding
caffeinate -i winetricks -q gecko
```

**`caffeinate -i` wraps this for the same reason as Step 4's download and Step 7's install** — `winetricks -q gecko` downloads and silently installs a real (if small) payload, and neither `winetricks` nor Wine requests its own "stay awake" assertion. On a laptop that's idle-timeout-eligible, an unlucky sleep mid-download can leave Gecko partially installed with no clear error pointing at why. `caffeinate` holds the assertion only as long as `winetricks` is running.

**Fallback, if winetricks isn't available or targets the wrong prefix — launch the patcher once on purpose and handle the prompt live:**

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
nohup wine64 "$GAME_DIR/UaRo Patcher.exe" >/tmp/uaro_patcher_gecko.log 2>&1 &
disown
```

**Background this one too, same reasoning as Step 7** — it waits on a human clicking a dialog, which can take longer than your tooling's command-execution timeout allows. Don't block on it; tell the user to watch for the dialog, then come back and check.

**Same window-focus caveat as Step 7 applies here too** — this dialog may not automatically pop to the front. Tell the user to check the Dock (or Cmd+Tab) if it doesn't appear right away, rather than assuming nothing happened.

When the "Wine Gecko Installer" dialog appears, **click Install** and wait for it to finish. **Never click Cancel.** (If driving this via computer-use/screen automation rather than a human at the keyboard: some Wine dialog windows don't reliably show up in screenshot/click pipelines gated by per-app permission allowlists even when the parent app is granted access — if a click can't be confirmed to land correctly, ask the human to click it directly rather than guessing coordinates.)

**MANDATORY verification, either path:** relaunch the patcher and confirm the status line advances past "Getting patch_main.txt..." and the panel actually renders/starts downloading. A blank panel still stuck on that line after a "successful" Gecko install means this step did not actually succeed — redo it before continuing.

**If the patcher instead crashes with a `Program Error` dialog right after Gecko finishes, that is a separate, already-known, unresolved open issue (see `TROUBLESHOOTING.md`) — not evidence this step failed.** Gecko itself installed correctly if you get this far; don't re-run this step or second-guess the install because of that crash.

## Step 9b — Fix in-game menu shortcuts (Cmd+A/Cmd+Z-style) not registering

**Category: Input/Keyboard**

**Root cause, confirmed by reading Wine's actual source, not a guess:** the game's menu-style shortcuts (item window, etc.) are built for a Windows `Alt+<letter>` scheme. Wine's mac driver already translates a bare physical `Cmd` key into `Alt` by default (`winemac.drv/keyboard.c`, `kVK_Command → VK_LMENU` — no setting needed for that part) — but Whisky's forked Wine (`winemac.drv/cocoa_app.m`) *also* injects a hidden "Edit" menu (Cut/Copy/Paste/Select All/Undo) into every Wine window, bound to `Cmd+X/C/V/A/Z`. macOS matches that menu's key equivalents *before* a keypress ever reaches the game — so specifically `Cmd+A` (Select All) and `Cmd+Z` (Undo) get swallowed by that hidden menu and never reach the game as `Alt+A`/`Alt+Z`, while unrelated combos like `Cmd+Q`/`Cmd+E` (not in that menu) pass straight through untouched. Same bug, same symptom, already reported upstream: [Whisky-App/Whisky#1060](https://github.com/Whisky-App/Whisky/issues/1060).

**Don't fix this by disabling the hidden Edit menu (`EditMenu` registry key) — that was tried and tested for real, and it works, but it breaks something else.** Disabling that menu does stop it from swallowing `Cmd+A`/`Cmd+Z`, but that same hidden menu is *also* what makes `Cmd+C`/`Cmd+V` paste correctly in the first place (by silently converting them into the `Ctrl+C`/`Ctrl+V` the game actually expects) — so disabling it trades one broken shortcut for another. **The actual fix is to stop using `Cmd` for these shortcuts at all, and use `Option` instead** — `Option` was never part of that hidden menu's shortcut list, so it was never at risk of being swallowed to begin with, and this matches how uaRO already behaves for anyone who's played it in a Windows VM (VMware Fusion, etc.), where `Option`/`Alt` has always been the key that triggers these shortcuts.

**Do this after Step 9, before the patcher/game is ever launched for real play** — and any time this symptom is reported on an existing install. These settings (both the check right below and the actual fix further down) are only read when a Wine window is created, so a fully closed game/bottle is required first — confirm that before touching either:

```bash
pgrep -f "Wine/bin/wine64-preloader" >/dev/null && echo "uaRO/Wine still running — close it first, this fix needs a clean bottle" || echo "Clean, safe to proceed"
```

**If this bottle previously had the old `EditMenu`-disable fix applied, undo it first** (check with `wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu` — any result at all, even empty, means it's set):

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
wine64 reg delete 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu /f 2>/dev/null || true
```

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt /t REG_SZ /d y /f
wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v RightOptionIsAlt /t REG_SZ /d y /f
wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt
wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v RightOptionIsAlt
```

**Tell the user plainly, every time this is applied:** in-game menu shortcuts now use **`Option+<letter>`, not `Cmd+<letter>`** (matches the VMware/Windows-VM experience). `Cmd+C`/`Cmd+V`/`Cmd+X` keep working exactly as before for copy/paste — nothing changes there, and there's no trade-off this time.

**A community fork's alternate approach is not a substitute for this fix either.** [frankea/Whisky](https://github.com/frankea/Whisky) added a "Map Command Key to Windows Ctrl" toggle claiming to close #1060, but it only sets `LeftCommandIsCtrl`/`RightCommandIsCtrl` — a setting that controls how an *already-delivered* Cmd keypress gets translated. It does nothing about the hidden Edit menu swallowing `Cmd+A`/`Cmd+Z` before that translation ever happens (confirmed by reading that fork's actual commit diff — it never touches `EditMenu`), so it doesn't fix this symptom, and setting `LeftCommandIsAlt`/`RightCommandIsAlt` (sometimes suggested alongside it) does nothing at all — those registry names don't exist anywhere in Wine's source; Wine never reads them.

## Step 10 — Write game config files

### `dinput.ini` (ROExt plugin) — at `$GAME_DIR/dinput.ini`

The installer already writes most of this correctly; only `WindowLock` typically needs flipping. Back up first, then patch just that key (don't regenerate the whole file blind — the installer's copy has useful comments):

```bash
if [[ -e "$GAME_DIR/dinput.ini.orig-backup" ]]; then
  [[ "$(stat -f%z "$GAME_DIR/dinput.ini")" == "$(stat -f%z "$GAME_DIR/dinput.ini.orig-backup")" ]] \
    || { echo "Existing dinput.ini backup has a different size — stop and inspect it before patching"; exit 1; }
  echo "Preserving existing original backup: $GAME_DIR/dinput.ini.orig-backup"
else
  cp "$GAME_DIR/dinput.ini" "$GAME_DIR/dinput.ini.orig-backup"
  echo "Created original backup: $GAME_DIR/dinput.ini.orig-backup"
fi
python3 -c "
import re, sys
p = '$GAME_DIR/dinput.ini'
s = open(p).read()
s = re.sub(r'WindowLock\s*=\s*0', 'WindowLock =1', s)
open(p, 'w').write(s)
"
grep -E 'MouseFreedom|WindowOnTop|WindowLock|CodePage' "$GAME_DIR/dinput.ini"
# Expect: MouseFreedom=1, WindowOnTop=0, WindowLock=1, CodePage=-1
```

### `savedata/OptionInfo.lua` — at `$GAME_DIR/savedata/OptionInfo.lua`

The installer ships a template with placeholder/default values. Back it up, then patch the fields below with a real script file or a **quoted** heredoc — never an unquoted one, since `DX9DEVICENAME`'s Windows device path is backslash-heavy and will silently corrupt otherwise.

```bash
if [[ -e "$GAME_DIR/savedata/OptionInfo.lua.orig-backup" ]]; then
  [[ "$(stat -f%z "$GAME_DIR/savedata/OptionInfo.lua")" == "$(stat -f%z "$GAME_DIR/savedata/OptionInfo.lua.orig-backup")" ]] \
    || { echo "Existing OptionInfo.lua backup has a different size — stop and inspect it before patching"; exit 1; }
  echo "Preserving existing original backup: $GAME_DIR/savedata/OptionInfo.lua.orig-backup"
else
  cp "$GAME_DIR/savedata/OptionInfo.lua" "$GAME_DIR/savedata/OptionInfo.lua.orig-backup"
  echo "Created original backup: $GAME_DIR/savedata/OptionInfo.lua.orig-backup"
fi
GUID="{$(uuidgen | tr a-z A-Z)}"
```

Write a small Python script **to a file** (not a heredoc, since the script body itself needs to write backslash-heavy content — see Section 0's heredoc warning) — **`<GAME_DIR>`, `<CHOSEN_WIDTH>`, `<CHOSEN_HEIGHT>` below are placeholders to substitute with real resolved values before this runs, same rule as Section 0's placeholder note and the worked `<UUID>` example in Step 5.** `guid` is deliberately *not* a placeholder here — `$GUID` was just computed as a real shell variable above, and the delimiter below must stay quoted (`<<'PYEOF'`) for `DX9DEVICENAME`'s backslash-heavy content a few lines down, which would block `$GUID` from interpolating even if written that way — so instead it's passed through the environment, read back via `os.environ`, avoiding a manual-retype step that's easy to fumble. The `cat > ... <<'PYEOF'` wrapper below is what actually creates the file — the script content shown isn't just illustrative, it's what gets written:

```bash
cat > /tmp/patch_optioninfo.py <<'PYEOF'
import os
import re
path = "<GAME_DIR>/savedata/OptionInfo.lua"
guid = os.environ["GUID"]   # set by $GUID at invocation below, not hand-typed -- see the note above this block
W, H = <CHOSEN_WIDTH>, <CHOSEN_HEIGHT>   # first-pass guess only — use the RESOLUTION parameter's auto-detected
                                          # native-display value from this file's Parameters table (Section 1,
                                          # not "Step 1" — see the Table of Contents note on the two numbering
                                          # schemes). Worked example: system_profiler prints
                                          # "Resolution: 3456 x 2234 Retina" -> W, H = 3456, 2234 (see the
                                          # RESOLUTION row's own note on parsing that line). Step 12 will
                                          # overwrite these correctly via RO OpenSetup's own Apply flow regardless

with open(path) as f:
    content = f.read()

def replace_kv(content, key, value, is_string=False):
    val_repr = f'"{value}"' if is_string else str(value)
    pattern = re.compile(r'(OptionInfoList\["' + re.escape(key) + r'"\]\s*=\s*)(?:"[^"]*"|-?\d+)')
    new_content, n = pattern.subn(lambda m: m.group(1) + val_repr, content)
    assert n == 1, f"expected exactly 1 match for {key}, got {n}"
    return new_content

content = replace_kv(content, "RENDERSYSTEM", 2)
content = replace_kv(content, "ISFULLSCREENMODE", 0)
content = replace_kv(content, "MouseExclusive", 0)
content = replace_kv(content, "WIDTH", W)
content = replace_kv(content, "HEIGHT", H)
content = replace_kv(content, "DX9DEVICEID", guid, is_string=True)
# DX9DEVICENAME must decode (via whatever parses this file) down to the literal path \\.\DISPLAY1
# — that requires the RAW FILE BYTES to contain 4 backslashes + dot + 2 backslashes:
content = replace_kv(content, "DX9DEVICENAME", "\\\\\\\\.\\\\DISPLAY1", is_string=True)

if 'OptionInfoList["OLD_WIDTH"]' not in content:
    content = content.replace(f'OptionInfoList["WIDTH"] = {W}\n',
                               f'OptionInfoList["WIDTH"] = {W}\nOptionInfoList["OLD_WIDTH"] = {W}\n')
if 'OptionInfoList["OLD_HEIGHT"]' not in content:
    content = content.replace(f'OptionInfoList["HEIGHT"] = {H}\n',
                               f'OptionInfoList["HEIGHT"] = {H}\nOptionInfoList["OLD_HEIGHT"] = {H}\n')

with open(path, "w") as f:
    f.write(content)
print("done")
PYEOF
GUID="$GUID" python3 /tmp/patch_optioninfo.py
```

If `$GUID` isn't set in this shell (a separate tool call from the one that ran `uuidgen` above), re-derive it the same way Section 0 describes for other step-local variables — don't hand-type a placeholder GUID, since that value must actually be unique per install.

**MANDATORY verification — don't eyeball it with `cat`, count the actual bytes:**

```bash
grep -n "DX9DEVICENAME" "$GAME_DIR/savedata/OptionInfo.lua"
# Raw line must read exactly:  OptionInfoList["DX9DEVICENAME"] = "\\\\.\\DISPLAY1"
# (4 backslashes, dot, 2 backslashes — count them character by character, grep/cat print raw bytes here)
python3 -c "print(repr(open('$GAME_DIR/savedata/OptionInfo.lua','rb').read()))" | grep -o 'DX9DEVICENAME[^,]*'
```

**Width/height set here are provisional.** RO OpenSetup's own GUI is the authoritative writer for resolution (its dropdown only offers a fixed list of scaled values tied to the real display, and hand-edited values here won't necessarily match what it shows). Treat the values above as a reasonable starting guess; Step 12 will overwrite them correctly via the app's own Apply flow.

## Phase D — Launchers & tooling (Step 11 + optional uaro-cli)

Build the three launcher `.app` bundles the user will actually double-click to play, plus an optional command-line helper for the same operations.

## Step 11 — Build the three launcher .app bundles

`UaRO Patcher.app` runs the patcher for daily play. `UaRO Settings.app` re-patches `setup.exe` then runs it, for graphics config — **players must never use the patcher's own in-app "Settings" button**, since `UaRo Patcher.exe` re-downloads any file whose hash mismatches its manifest, including the patched `setup.exe`, and the patcher's own Settings button runs the (by-then-unpatched) file directly. `UaRO Game.app` skips the patcher entirely and launches `uaRO.exe` directly — see its own section below for what this trades away.

**Naming note:** the patcher launcher was named plain `UaRO.app` before 2026-07-27 — it was renamed to `UaRO Patcher.app` (bundle, `Info.plist` fields, and script filename `uaro-launch` → `uaro-patcher`) so all three launchers' names describe what each one actually does, rather than one being unlabeled. See Step 2a for the migration check on existing installs still carrying the old name.

**Standing rule, not just for this initial build: any future fix that touches one launcher's script content (`uaro-patcher`, `uaro-settings`, or `uaro-game`) must be applied to all three where it's actually relevant**, unless the fix is genuinely specific to one (e.g. the crash-dialog mitigation and the patch-check both only apply to `uaro-patcher`, since only it runs the patcher). Whenever any of the three scripts is edited after this initial build — including by Step 2a's healing checks, or by any later session — **re-sign that bundle afterward** (see the `codesign` step below); an unsigned or stale-signed bundle after edits is the kind of thing that works today and silently breaks on a future macOS update.

**Before building anything below — ask about `UaRO Game.app` specifically, every time this step runs (a fresh install, not just a Step 2a retrofit on an existing one).** It's the one launcher with an accepted, unresolved risk (see its own note further down, and `TROUBLESHOOTING.md`) — `UaRO Patcher.app`/`UaRO Settings.app` carry no such trade-off and don't need this checkpoint. Ask something like: *"There's an optional third launcher, `UaRO Game`, that skips the patcher for a faster relaunch — but it has no way to detect a stale/unpatched client if a patch ships while it's being used instead of the Patcher. Want me to build it along with the other two, or just Patcher + Settings for now?"*

**Set `$APPS` right after that answer — it's the single toggle every command below reads from, so there's no separate place to remember to drop `UaRO Game.app` from.** Set it and use it for the `mkdir` below in the same shell invocation:

```bash
if [[ "$BUILD_GAME_APP" == "yes" ]]; then   # "yes"/"no" based on the answer just given -- not a Section 1 parameter
  APPS=("UaRO Patcher.app" "UaRO Settings.app" "UaRO Game.app")
else
  APPS=("UaRO Patcher.app" "UaRO Settings.app")
fi
for APP in "${APPS[@]}"; do
  mkdir -p "/Applications/$APP/Contents/MacOS"
done
```

Every loop and command for the rest of this step iterates `"${APPS[@]}"` rather than naming bundles literally, so a declined `UaRO Game.app` is simply never in the array — nothing else in this step needs to know the decision was made. It can always be added later via Step 2a's own migration check, which asks this same question for existing installs.

**`$APPS` is not on Section 0's list of things safe to assume persist — re-derive it at the top of every later block in this step, the same way as `$BOTTLE_NAME`/`$GAME_DIR`.** Don't re-ask the user or re-run the `if`/`else` above from memory — the `mkdir` loop just above already created (or didn't create) `/Applications/UaRO Game.app` on disk, so later blocks can check that directly instead of trusting a remembered decision:

```bash
APPS=("UaRO Patcher.app" "UaRO Settings.app")
[[ -d "/Applications/UaRO Game.app" ]] && APPS+=("UaRO Game.app")
```

This one-liner is safe to paste at the top of any later block in this step that uses `$APPS` — in bash it's a genuine no-op if `$APPS` is already correctly set (reassigning the same array), and it works whether or not this is a fresh shell invocation, so there's no need to first check whether re-derivation is actually necessary.

`Info.plist` (`name`/`display name`/`identifier`/`executable` differ per bundle, everything else about the XML is identical) — generated for all three bundles in `$APPS` by one loop, rather than shown once for `UaRO Patcher.app` and left to be mirrored by hand for the other two (that hand-mirroring is exactly how a `CFBundleName` update misses its `CFBundleDisplayName` sibling, leaving a bundle displaying "UaRO Patcher" in Finder/Get Info while actually being `UaRO Settings.app`). **This heredoc is deliberately unquoted (`<<PLIST`, not `<<'PLIST'`)** — unlike the launcher scripts and `uaro-cli` further down, this content has no backslash-heavy data needing protection, and unquoted lets `$NAME`/`$ID`/`$EXEC` interpolate per iteration instead of being hand-edited three times:

```bash
APPS=("UaRO Patcher.app" "UaRO Settings.app")   # re-derive $APPS -- see the note after the mkdir loop above
[[ -d "/Applications/UaRO Game.app" ]] && APPS+=("UaRO Game.app")

for APP in "${APPS[@]}"; do
  case "$APP" in
    "UaRO Patcher.app")  NAME="UaRO Patcher";  ID="com.uaro.patcher";  EXEC="uaro-patcher" ;;
    "UaRO Settings.app") NAME="UaRO Settings"; ID="com.uaro.settings"; EXEC="uaro-settings" ;;
    "UaRO Game.app")     NAME="UaRO Game";     ID="com.uaro.game";     EXEC="uaro-game" ;;
  esac
  cat > "/Applications/$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>$NAME</string>
	<key>CFBundleDisplayName</key><string>$NAME</string>
	<key>CFBundleIdentifier</key><string>$ID</string>
	<key>CFBundleVersion</key><string>1.0</string>
	<key>CFBundleShortVersionString</key><string>1.0</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleIconFile</key><string>AppIcon.icns</string>
	<key>CFBundleExecutable</key><string>$EXEC</string>
	<key>LSMinimumSystemVersion</key><string>11.0</string>
	<key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST
done
```

Without `CFBundleIconFile` (and a matching icon actually placed in `Contents/Resources/`), all three apps silently fall back to the generic blank-document icon — easy to miss since nothing errors, it just looks unfinished in Launchpad/Dock.

`UaRO Patcher.app/Contents/MacOS/uaro-patcher` — **`<BOTTLE_NAME>` and `<GAME_DIR>` must be substituted with this machine's real resolved values before this file is written to disk; the app has no shell variables to fall back on when the user later double-clicks it.** The `cat > ... <<'EOF'` wrapper below is what actually creates the file — **the heredoc delimiter must stay quoted (`<<'EOF'`, not `<<EOF`)**, since the script body below has its own live `$pid`/`$code`/`$attempt`/`$WINEDLLOVERRIDES` variables that must reach disk literally, for `zsh` to evaluate when the app is later double-clicked — not get expanded by *this* shell at write time:

```bash
cat > "/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher" <<'EOF'
#!/bin/zsh
set -e
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv <BOTTLE_NAME>)"
cd "<GAME_DIR>"

# Clear out any stale Wine processes from a previous session that didn't fully
# close (crashed, force-quit, etc.) before starting a new one -- wineserver -k
# only tears down the server for this bottle's own WINEPREFIX (already scoped
# by the shellenv eval above), so this doesn't touch any other bottle.
wineserver -k >/dev/null 2>&1 || true
pkill -f "UaRo Patcher.exe" >/dev/null 2>&1 || true
pkill -f "uaRO.exe" >/dev/null 2>&1 || true
sleep 1

export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:+$WINEDLLOVERRIDES;}msvcp140,vcruntime140,concrt140,vccorlib140=n,b"
export WINE_CPU_TOPOLOGY=4:0,1,2,3

# Suppress Wine's graphical crash dialog -- combined with the retry loop below,
# the known false-positive patcher crash (see TROUBLESHOOTING.md) gets silently
# retried once instead of popping an alarming "Program Error" window.
wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\WineDbg' /v ShowCrashDialog /t REG_DWORD /d 0 /f >/dev/null 2>&1 || true

attempt=1
code=0
while [[ $attempt -le 2 ]]; do
    start=$(date +%s)
    wine64 "UaRo Patcher.exe" >/dev/null 2>&1 &
    pid=$!
    # set +e/-e bracketing `wait` is load-bearing, not decoration: with `set -e` active
    # (as at the top of this script), `wait $pid` on a non-zero exit triggers errexit
    # itself -- the script would terminate right there, before `code=$?` ever runs, so
    # the retry below silently never fires on the very first crash. Confirmed directly:
    # `zsh -c 'set -e; false & wait $!; echo reached'` never prints "reached".
    set +e
    wait $pid
    code=$?
    set -e
    elapsed=$(( $(date +%s) - start ))

    # If the patcher exited by handing off to the game (user clicked Launch
    # Game), uaRO.exe is running now -- that's success, not a crash, even
    # though the handoff kills the patcher with a non-zero status (observed
    # live: exit 137/SIGKILL, 44s after launch). Without this check, any
    # sub-60s handoff matches the retry heuristic below exactly and spawns a
    # ghost second patcher next to the launching game. The stale-process
    # cleanup at the top of this script pkills uaRO.exe, so if it's running
    # here, this patcher session started it. sleep first: give the freshly
    # spawned game process a moment to be reliably visible to pgrep.
    sleep 2
    if pgrep -f "uaRO.exe" >/dev/null 2>&1; then
        code=0
        break
    fi

    # A clean user-initiated quit exits 0. The known false-positive crash gets
    # killed with the exception code as its exit status (a large, distinctly
    # abnormal number) and happens early after launch -- retry once in that
    # specific case only, never in a loop.
    if [[ $code -eq 0 || $elapsed -ge 60 || $attempt -eq 2 ]]; then
        break
    fi
    attempt=$((attempt + 1))
done
exit $code
EOF
```

**Why this doesn't cost anything while the game is running:** `wait $pid` is a blocking call on the process's actual exit, not a poll loop — this script spends zero CPU while the patcher/game session is active, and the wrapper process itself disappears the moment the session ends (confirmed on a real machine: no lingering process, no measurable CPU/memory footprint). Don't rewrite this as a `sleep`-and-check polling loop; that would burn CPU for no reason across a long play session.

**Verified fix, not theoretical** — applied to a real launcher, then deliberately reproduced the known post-Gecko patcher crash: no "Program Error" dialog appeared, and the wrapper script exited cleanly once the session ended, with nothing left running in the background afterward.

`WINEDLLOVERRIDES` **must append**, never replace — `whisky shellenv` already exports DXVK overrides (`dxgi,d3d9,d3d10core,d3d11=n,b`); overwriting the variable disables DXVK and tanks FPS. `WINE_CPU_TOPOLOGY=4:0,1,2,3` stabilizes Gepard Shield's anti-debug CPU-detection routines (fixes crashes ~3s after login and `Gepard::T Code: 3::110::12` disconnects).

`UaRO Settings.app/Contents/MacOS/uaro-settings` uses the same substitution rule and quoted-heredoc requirement as `uaro-patcher` above. Its only active implementation is the bundle-local route below; the former inline byte-edit launcher has been retired so a Finder launch cannot select a second FCOM mutation HOW.

### Stage 2.2B — bundle-local Settings route

The bundle-local Settings launcher below is the sole active Step 11 Settings route. It keeps the launcher decision and FCOM mutation evidence in the bundle-local runtime:

```text
Finder / LaunchServices
        -> UaRO Settings.app
        -> recorded absolute Python
        -> bundle-local settings_runtime_verify.py
        -> runtime PASS
        -> bundled uaro.py fcom apply "$SETUP"
        -> validate apply evidence
        -> independent bundled fcom check "$SETUP"
        -> require PATCHED
        -> launch setup.exe
```

Build the runtime after `UaRO Settings.app` exists and while the canonical
sources are committed and clean. The recorded interpreter path is embedded in
the launcher so a later Finder launch never searches `PATH`:

```bash
AURO_REPO_ROOT="${AURO_REPO_ROOT:?Resolve this checkout before building the Settings runtime}"
PYTHON_RUNTIME="$(python3 -c 'import os,sys; print(os.path.abspath(sys.executable))')"
RUNTIME_DIR="/Applications/UaRO Settings.app/Contents/Resources/uaro-runtime"
python3 "$AURO_REPO_ROOT/scripts/build_settings_runtime.py" build \
  --repo-root "$AURO_REPO_ROOT" \
  --destination "$RUNTIME_DIR" \
  --python "$PYTHON_RUNTIME"
```

Write the following as the deterministic implementation for
`/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings`. Replace every
angle-bracket placeholder before writing the file; the quoted heredoc keeps the
runtime variables literal for the later Finder launch.

```bash
cat > "/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings" <<'EOF'
#!/bin/zsh
set -e
BOTTLE_NAME="<BOTTLE_NAME>"
GAME_DIR="<GAME_DIR>"
PYTHON_RUNTIME="<RECORDED_PYTHON>"
RUNTIME_DIR="<RUNTIME_DIR>"
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv "$BOTTLE_NAME")"
cd "$GAME_DIR"

[[ -x "$PYTHON_RUNTIME" ]] || { echo "BLOCKED: recorded Python is missing or not executable" >&2; exit 1; }
[[ -f "$RUNTIME_DIR/MANIFEST.json" && -f "$RUNTIME_DIR/uaro.py" && -f "$RUNTIME_DIR/settings_runtime_verify.py" ]] || {
  echo "BLOCKED: bundled Settings runtime is incomplete" >&2
  exit 1
}

RUNTIME_JSON="$("$PYTHON_RUNTIME" "$RUNTIME_DIR/settings_runtime_verify.py" "$RUNTIME_DIR")" || {
  echo "BLOCKED: bundle-local Settings runtime verification failed" >&2
  exit 1
}
if ! "$PYTHON_RUNTIME" - "$RUNTIME_JSON" <<'PYEOF'
import json
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed runtime verification evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
if payload.get("result") != "PASS":
    print("BLOCKED: bundled Settings runtime did not PASS", file=sys.stderr)
    raise SystemExit(1)
for key in ("executor_verified", "verifier_verified", "python_verified"):
    if payload.get(key) is not True:
        print(f"BLOCKED: runtime verification omitted {key}", file=sys.stderr)
        raise SystemExit(1)
PYEOF
then
  exit 1
fi

SETUP="$GAME_DIR/setup.exe"
[[ -f "$SETUP" ]] || { echo "BLOCKED: setup.exe is missing" >&2; exit 1; }

validate_bundled_executor_json() {
  local payload="$1"
  local expected_operation="$2"
  local expected_path_key="$3"
  local expected_path="$4"
  local expected_capability="$5"
  local validation_mode="$6"
  "$PYTHON_RUNTIME" - "$payload" "$expected_operation" "$expected_path_key" "$expected_path" "$expected_capability" "$validation_mode" <<'PYEOF'
import json
import os
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed bundled executor JSON: {exc}", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(payload, dict):
    print("BLOCKED: bundled executor JSON is not an object", file=sys.stderr)
    raise SystemExit(1)
expected_operation, expected_path_key, expected_path = sys.argv[2:5]
expected_capability, validation_mode = sys.argv[5:7]
required = ("operation", "capability", "result", "mutation")
missing = [key for key in required if key not in payload]
if missing:
    print(f"BLOCKED: incomplete bundled executor evidence: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
if payload["operation"] != expected_operation or payload["result"] != "success":
    print("BLOCKED: bundled executor returned an unexpected result", file=sys.stderr)
    raise SystemExit(1)
if validation_mode == "readonly" and payload["mutation"] is not False:
    print("BLOCKED: independent FCOM check was not read-only", file=sys.stderr)
    raise SystemExit(1)
if validation_mode == "apply" and not isinstance(payload["mutation"], bool):
    print("BLOCKED: FCOM apply evidence has no boolean mutation field", file=sys.stderr)
    raise SystemExit(1)
if payload.get("capability") != expected_capability:
    print("BLOCKED: bundled executor returned an unexpected capability", file=sys.stderr)
    raise SystemExit(1)
reported_path = payload.get(expected_path_key)
if not isinstance(reported_path, str):
    print("BLOCKED: bundled executor omitted its target path", file=sys.stderr)
    raise SystemExit(1)
if os.path.realpath(os.path.abspath(reported_path)) != os.path.realpath(os.path.abspath(expected_path)):
    print("BLOCKED: bundled executor named a different target", file=sys.stderr)
    raise SystemExit(1)
print(json.dumps(payload, sort_keys=True))
PYEOF
}

wineserver -k >/dev/null 2>&1 || true
pkill -f "UaRo Patcher.exe" >/dev/null 2>&1 || true
pkill -f "uaRO.exe" >/dev/null 2>&1 || true
pkill -f "setup.exe" >/dev/null 2>&1 || true
sleep 1

export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:+$WINEDLLOVERRIDES;}msvcp140,vcruntime140,concrt140,vccorlib140=n,b"
export WINE_CPU_TOPOLOGY=4:0,1,2,3

if ! CHECK_JSON="$("$PYTHON_RUNTIME" "$RUNTIME_DIR/uaro.py" fcom check "$SETUP")"; then
  echo "BLOCKED: bundled pre-apply FCOM check failed" >&2
  exit 1
fi
if ! CHECK_JSON="$(validate_bundled_executor_json "$CHECK_JSON" "fcom-check" "target" "$SETUP" "READ" "readonly")"; then
  exit 1
fi
if ! CHECK_STATE="$("$PYTHON_RUNTIME" - "$CHECK_JSON" <<'PYEOF'
import json
import sys

payload = json.loads(sys.argv[1])
required = ("state", "site_a", "site_b", "backup_created", "verification")
if any(key not in payload for key in required):
    print("BLOCKED: incomplete pre-apply FCOM evidence", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] not in ("UNPATCHED", "PATCHED"):
    print("BLOCKED: pre-apply FCOM state is not safely classifiable", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] == "UNPATCHED" and (payload["site_a"] != "unpatched" or payload["site_b"] != "unpatched"):
    print("BLOCKED: pre-apply FCOM site evidence disagrees", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] == "PATCHED" and (payload["site_a"] != "patched" or payload["site_b"] != "patched"):
    print("BLOCKED: pre-apply FCOM site evidence disagrees", file=sys.stderr)
    raise SystemExit(1)
if payload["backup_created"] is not False or payload["verification"] != "not-run":
    print("BLOCKED: pre-apply check claimed mutation", file=sys.stderr)
    raise SystemExit(1)
print(payload["state"])
PYEOF
)"; then
  exit 1
fi

if [[ "$CHECK_STATE" == "UNPATCHED" ]]; then
  if ! APPLY_JSON="$("$PYTHON_RUNTIME" "$RUNTIME_DIR/uaro.py" fcom apply "$SETUP")"; then
    echo "BLOCKED: bundled FCOM apply failed" >&2
    exit 1
  fi
  if ! APPLY_JSON="$(validate_bundled_executor_json "$APPLY_JSON" "fcom-apply" "target" "$SETUP" "REVERSIBLE_MUTATION" "apply")"; then
    exit 1
  fi
  if ! "$PYTHON_RUNTIME" - "$APPLY_JSON" <<'PYEOF'
import json
import sys

payload = json.loads(sys.argv[1])
required = ("state", "pre_state", "post_state", "site_a", "site_b", "backup_created", "mutation", "verification", "reason")
if any(key not in payload for key in required):
    print("BLOCKED: incomplete FCOM apply evidence", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] not in ("UNPATCHED", "PATCHED") or payload["post_state"] != "PATCHED":
    print("BLOCKED: FCOM apply did not prove PATCHED", file=sys.stderr)
    raise SystemExit(1)
if payload["state"] != payload["pre_state"] or payload["verification"] != "passed":
    print("BLOCKED: FCOM apply evidence is incoherent", file=sys.stderr)
    raise SystemExit(1)
if payload["reason"] not in ("patched and verified", "already patched; no-op"):
    print("BLOCKED: FCOM apply returned an unrecognized success reason", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] == "UNPATCHED" and payload["mutation"] is not True:
    print("BLOCKED: UNPATCHED apply did not report mutation", file=sys.stderr)
    raise SystemExit(1)
if payload["pre_state"] == "PATCHED" and (payload["mutation"] is not False or payload["backup_created"] is not False):
    print("BLOCKED: no-op apply claimed mutation or backup", file=sys.stderr)
    raise SystemExit(1)
PYEOF
  then
    exit 1
  fi

  if ! POST_CHECK_JSON="$("$PYTHON_RUNTIME" "$RUNTIME_DIR/uaro.py" fcom check "$SETUP")"; then
    echo "BLOCKED: independent post-apply FCOM check failed" >&2
    exit 1
  fi
  if ! POST_CHECK_JSON="$(validate_bundled_executor_json "$POST_CHECK_JSON" "fcom-check" "target" "$SETUP" "READ" "readonly")"; then
    exit 1
  fi
  if ! "$PYTHON_RUNTIME" - "$POST_CHECK_JSON" <<'PYEOF'
import json
import sys

payload = json.loads(sys.argv[1])
if payload.get("state") != "PATCHED" or payload.get("site_a") != "patched" or payload.get("site_b") != "patched":
    print("BLOCKED: independent FCOM check did not prove PATCHED", file=sys.stderr)
    raise SystemExit(1)
if payload.get("mutation") is not False or payload.get("backup_created") is not False or payload.get("verification") != "not-run":
    print("BLOCKED: independent post-apply check claimed mutation", file=sys.stderr)
    raise SystemExit(1)
PYEOF
  then
    exit 1
  fi
  echo "FCOM apply and independent PATCHED check passed"
elif [[ "$CHECK_STATE" != "PATCHED" ]]; then
  echo "BLOCKED: pre-apply FCOM state=$CHECK_STATE" >&2
  exit 1
fi

exec wine64 "setup.exe" >/dev/null 2>&1
EOF
```

This route has no inline FCOM fallback. A verifier `PASS` is only
deployment evidence; the explicit `fcom apply` result and the independent
read-only `fcom check` must both prove the final `PATCHED` state before
`setup.exe` is launched. Re-sign the app after installing this deterministic script.

`UaRO Game.app/Contents/MacOS/uaro-game` — same substitution rule and quoted-heredoc requirement as `uaro-patcher` above, same stale-process cleanup, but skips the patcher entirely and execs `uaRO.exe` directly:

```bash
cat > "/Applications/UaRO Game.app/Contents/MacOS/uaro-game" <<'EOF'
#!/bin/zsh
set -e
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
eval "$("$WHISKY" shellenv <BOTTLE_NAME>)"
cd "<GAME_DIR>"

# Same stale-process cleanup as uaro-patcher/uaro-settings -- see those scripts for why.
wineserver -k >/dev/null 2>&1 || true
pkill -f "UaRo Patcher.exe" >/dev/null 2>&1 || true
pkill -f "uaRO.exe" >/dev/null 2>&1 || true
sleep 1

export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:+$WINEDLLOVERRIDES;}msvcp140,vcruntime140,concrt140,vccorlib140=n,b"
export WINE_CPU_TOPOLOGY=4:0,1,2,3

wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\WineDbg' /v ShowCrashDialog /t REG_DWORD /d 0 /f >/dev/null 2>&1 || true

exec wine64 "uaRO.exe"
EOF
```

**Known, unresolved risk — read before relying on this for real play.** `UaRO Game.app` never talks to the patcher, so it never checks for or downloads new patches. Confirmed (2026-07-27, one real machine) that this launches cleanly, produces a stable process tree, and reaches a working login on a bottle that was already fully up to date — **but there is no known way to verify whether `uaRO.exe` enforces its own version check.** If the server ships a new patch and this bottle hasn't run `UaRO Patcher.app` since, this script has no way of detecting that and will silently launch whatever's already on disk, which could be a stale client. This has not been tested across an actual patch cycle. **Recommended use:** run `UaRO Patcher.app` at least once per session (or whenever a patch is known to have shipped), and treat `UaRO Game.app` as a faster relaunch option in between — not a permanent replacement for the patcher. See `TROUBLESHOOTING.md` for the formal writeup of this risk.

### App icon (extract from the game's own files — do not fabricate/download one)

The game already ships a usable icon; all three launcher `.app`s just need it pulled out and converted. Requires `icoutils` (`brew install icoutils`, gives `wrestool`/`icotool`):

```bash
brew install icoutils   # idempotent if already present

ICON_TMP="$(mktemp -d)"
cd "$ICON_TMP"

# UaRo Patcher.exe embeds a 48x48 24-bit true-color icon (group_icon --name=1) —
# the highest-quality source available; the standalone icnbig.ico files in
# $GAME_DIR are the same resolution but 8-bit indexed color, so prefer the exe.
wrestool -x --output=patcher_main.ico --type=14 --name=1 "$GAME_DIR/UaRo Patcher.exe"

# Extract by explicit --index, not a guessed filename pattern — icotool's
# auto-naming (e.g. patcher_main_1_48x48x24.png) isn't guaranteed across
# versions. `icotool -l` lists what's actually inside; take --index=1
# (there's normally only one icon in this particular resource) and give
# it a name we control:
icotool -l patcher_main.ico
# ^ if this ever lists more than one --icon entry, pick the largest --width
#   and pass that entry's --index below instead of assuming 1.
icotool -x --index=1 -o patcher_48.png patcher_main.ico
SRC=patcher_48.png

mkdir -p UaRO.iconset
for spec in "16 16" "32 16@2x" "32 32" "64 32@2x" "128 128" "256 128@2x" "256 256" "512 256@2x" "512 512" "1024 512@2x"; do
	size=$(echo $spec | cut -d' ' -f1); name=$(echo $spec | cut -d' ' -f2)
	sips -z $size $size "$SRC" --out "UaRO.iconset/icon_${name}.png" >/dev/null
done
iconutil -c icns UaRO.iconset -o AppIcon.icns

APPS=("UaRO Patcher.app" "UaRO Settings.app")   # re-derive $APPS -- see the note after the mkdir loop above
[[ -d "/Applications/UaRO Game.app" ]] && APPS+=("UaRO Game.app")
for APP in "${APPS[@]}"; do
	mkdir -p "/Applications/$APP/Contents/Resources"
	cp AppIcon.icns "/Applications/$APP/Contents/Resources/AppIcon.icns"
done
```

The source PNG is only 48×48 (nothing higher-res is embedded anywhere in the game files), so `sips` is upscaling for the 256/512/1024 tiers — it'll look a little soft at the largest Launchpad/Finder preview sizes, but is fine for a desktop shortcut. This step can run any time after `$GAME_DIR` is populated (Step 6 onward) and before the final `lsregister -f` below, since that call is what makes Launch Services notice the new icon — if the apps were already registered without an icon, re-run `lsregister -f` plus `killall Dock; killall Finder` to bust the icon cache after adding it later.

```bash
APPS=("UaRO Patcher.app" "UaRO Settings.app")   # re-derive $APPS -- see the note after the mkdir loop above
[[ -d "/Applications/UaRO Game.app" ]] && APPS+=("UaRO Game.app")
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

for APP in "${APPS[@]}"; do
  # A case statement, not an associative array -- typeset -A/declare -A needs bash 4+
  # or zsh, but this whole file is fenced as plain ```bash and macOS's actual /bin/bash
  # is still 3.2, which rejects -A outright. case is portable to both.
  case "$APP" in
    "UaRO Patcher.app")  EXE="uaro-patcher" ;;
    "UaRO Settings.app") EXE="uaro-settings" ;;
    "UaRO Game.app")     EXE="uaro-game" ;;
  esac

  chmod +x "/Applications/$APP/Contents/MacOS/$EXE"
  plutil -lint "/Applications/$APP/Contents/Info.plist"
  zsh -n "/Applications/$APP/Contents/MacOS/$EXE"

  # Ad-hoc re-sign -- a freshly-built, never-signed bundle usually still
  # launches fine locally (no quarantine attribute to trigger a strict Gatekeeper
  # check), but that's a latent gap, not a guarantee: any future edit to any
  # bundle's contents (this step, Step 2a's healing checks, or a later session)
  # should re-run this same codesign call afterward, not just the first build.
  codesign --force --deep --sign - "/Applications/$APP"

  # Backup copy inside the game folder, per the original design intent
  cp -R "/Applications/$APP" "$GAME_DIR/$APP"

  "$LSREGISTER" -f "/Applications/$APP"
done
```

**MANDATORY registration verification — never `mdls`/`mdfind`, Spotlight lags well behind actual registration and will falsely report nothing for a while:**

```bash
"$LSREGISTER" -dump 2>/dev/null | grep -A2 "identifier:.*com.uaro"
```

**MANDATORY local signature-integrity check — confirm the bundle has a valid ad-hoc signature and make the trust boundary explicit.** This proves the bundle's current code signature is internally valid after our local edit; it does **not** establish an Apple developer identity, notarization, or upstream provenance:

```bash
APPS=("UaRO Patcher.app" "UaRO Settings.app")   # re-derive $APPS -- see the note after the mkdir loop above
[[ -d "/Applications/UaRO Game.app" ]] && APPS+=("UaRO Game.app")
for APP in "${APPS[@]}"; do
  BUNDLE="/Applications/$APP"
  if ! codesign --verify --deep --strict "$BUNDLE" >/dev/null 2>&1; then
    echo "FAILED: $APP local code-signature verification failed"
  elif codesign -dv "$BUNDLE" 2>&1 | grep -q "not signed"; then
    echo "FAILED: $APP still unsigned"
  else
    echo "OK: $APP local ad-hoc signature verified (signer trust/notarization unestablished)"
  fi
done
```

## Optional: uaro-cli command-line helper

A small convenience wrapper around three operations this file otherwise documents doing by hand: force-quitting stuck processes, launching the game, and diagnosing/repairing the launcher bundles. Purely optional — the game works fully without it — but cheap to build, since it just calls the same commands Step 11 and this section already use elsewhere in this file, with no new risk of its own (unlike `UaRO Game.app`, it has no accepted trade-off). Build it as part of Step 11, right after the three launcher bundles are signed and registered.

`repair` specifically **diagnoses before it fixes**, rather than blindly re-running codesign/lsregister regardless of whether anything was actually wrong: it checks the game install and bottle exist, then per launcher checks the executable bit, script syntax, whether the script predates the `command -v whisky` fallback fix, `Info.plist` validity, and reads back the actual signature/registration state after attempting to fix them. Only the mechanical stuff (permissions, signature, registration) gets auto-fixed — anything else (bad syntax, a stale pre-fix script, a broken plist, a missing bottle) just gets flagged with a pointer back to Step 11, since rewriting script *content* automatically is a different (and riskier) kind of operation than the reversible, idempotent fixes this tool is meant for.

**If anything couldn't be auto-fixed, `repair` doesn't just print `[WARN]` lines and stop there** — it collects them into a final numbered list, prints a ready-to-paste message pointing whoever's reading it at Step 11 (so the next step is "copy this to a Claude Code/Codex session," not "go figure out which section of SKILL.md applies"), and exits with status `1` (a clean run exits `0`) so the outcome is also detectable by anything scripting against `uaro-cli`, not only by a human reading the terminal output.

**`<BOTTLE_NAME>` and `<GAME_DIR>` must be substituted with this machine's real resolved values before this file is written to disk**, same as the launcher scripts above — this script has no shell variables to fall back on once installed. The `cat > ... <<'SCRIPT'` wrapper below both shows the content and is what actually creates the file at `/opt/homebrew/bin/uaro-cli` — already on `PATH` since Step 1, and already where `whisky` itself lives, so no separate `PATH` edit or shell-profile change is needed. **Keep the heredoc delimiter quoted (`<<'SCRIPT'`)** — the script body has its own live `$BOTTLE_NAME`/`$problems`/`$i` etc. variables that must reach disk literally for `zsh` to evaluate later, not get expanded by *this* shell at write time:

```bash
cat > /opt/homebrew/bin/uaro-cli <<'SCRIPT'
#!/bin/zsh
set -e

BOTTLE_NAME="<BOTTLE_NAME>"
GAME_DIR="<GAME_DIR>"
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"

usage() {
    cat <<'EOF'
uaro-cli — command-line helper for the uaRO Whisky install

Usage:
  uaro-cli kill      Force-quit any running uaRO/Wine processes for this bottle
  uaro-cli launch    Launch the game (same as double-clicking UaRO Patcher.app)
  uaro-cli repair    Diagnose all installed launcher .app bundles, auto-fix what's
                      safely fixable (missing executable bit, stale signature,
                      missing Launch Services registration), and flag anything
                      else (bad script syntax, a pre-fix launcher, a broken
                      Info.plist, a missing bottle/game install) for a Step 11
                      rebuild instead of guessing at it
EOF
}

cmd_kill() {
    eval "$("$WHISKY" shellenv "$BOTTLE_NAME")" 2>/dev/null || true
    wineserver -k >/dev/null 2>&1 || true
    pkill -f "UaRo Patcher.exe" >/dev/null 2>&1 || true
    pkill -f "uaRO.exe" >/dev/null 2>&1 || true
    pkill -f "setup.exe" >/dev/null 2>&1 || true
    echo "Killed any running uaRO/Wine processes for bottle '$BOTTLE_NAME'."
}

cmd_launch() {
    open "/Applications/UaRO Patcher.app"
}

cmd_repair() {
    local problems=0
    local -a issues

    echo "-- Game install --"
    if [[ -f "$GAME_DIR/uaRO.exe" ]]; then
        echo "[OK]   uaRO.exe found at \$GAME_DIR"
    else
        echo "[WARN] uaRO.exe not found at $GAME_DIR -- game isn't actually installed there"
        problems=$((problems + 1))
        issues+=("Game files missing at $GAME_DIR -- re-run Step 6/7 to (re)install the game, or check GAME_DIR is set correctly")
    fi

    if "$WHISKY" list 2>/dev/null | grep -q "$BOTTLE_NAME"; then
        echo "[OK]   Bottle '$BOTTLE_NAME' exists"
    else
        echo "[WARN] Bottle '$BOTTLE_NAME' not found via 'whisky list' -- launchers will fail until it's recreated (Step 5)"
        problems=$((problems + 1))
        issues+=("Bottle '$BOTTLE_NAME' missing -- recreate it via Step 5")
    fi

    local required=0
    local exe_name
    for APP in "UaRO Patcher.app" "UaRO Settings.app" "UaRO Game.app"; do
        case "$APP" in
            "UaRO Patcher.app"|"UaRO Settings.app") required=1 ;;
            "UaRO Game.app") required=0 ;;
        esac

        local bundle="/Applications/$APP"
        if [[ ! -d "$bundle" ]]; then
            if [[ $required -eq 1 ]]; then
                echo "[WARN] Required launcher missing: $APP"
                problems=$((problems + 1))
                issues+=("$APP: required launcher is missing -- rebuild via Step 11")
            else
                echo "-- $APP -- [--] optional launcher not installed, skipping"
            fi
            continue
        fi
        echo "-- $APP --"

        local plist="$bundle/Contents/Info.plist"
        case "$APP" in
            "UaRO Patcher.app")  exe_name="uaro-patcher" ;;
            "UaRO Settings.app") exe_name="uaro-settings" ;;
            "UaRO Game.app")     exe_name="uaro-game" ;;
        esac
        local exe="$bundle/Contents/MacOS/$exe_name"

        if [[ ! -f "$exe" ]]; then
            echo "[WARN] $exe missing entirely -- rebuild this launcher per SKILL.md Step 11"
            problems=$((problems + 1))
            issues+=("$APP: executable missing entirely -- rebuild via Step 11")
            continue
        fi

        if [[ -x "$exe" ]]; then
            echo "[OK]   Executable bit set"
        else
            chmod +x "$exe" 2>/dev/null || true
            echo "[FIXED] Executable bit was missing -- restored"
        fi

        if zsh -n "$exe" 2>/dev/null; then
            echo "[OK]   Script syntax valid"
        else
            echo "[WARN] Script has a syntax error -- rebuild this launcher per SKILL.md Step 11"
            problems=$((problems + 1))
            issues+=("$APP: script has a syntax error -- rebuild via Step 11")
        fi

        if grep -q 'command -v whisky' "$exe" 2>/dev/null; then
            echo "[OK]   Uses the command -v whisky fallback (not hardcoded to one path)"
        else
            echo "[WARN] Predates the command -v whisky fallback fix -- rebuild per SKILL.md Step 11"
            problems=$((problems + 1))
            issues+=("$APP: predates the command -v whisky fallback fix -- rebuild via Step 11")
        fi

        if plutil -lint "$plist" >/dev/null 2>&1; then
            echo "[OK]   Info.plist valid"
        else
            echo "[WARN] Info.plist invalid -- rebuild this launcher per SKILL.md Step 11"
            problems=$((problems + 1))
            issues+=("$APP: Info.plist invalid -- rebuild via Step 11")
        fi

        if ! codesign --force --deep --sign - "$bundle" >/dev/null 2>&1; then
            echo "[WARN] Re-sign command failed"
            problems=$((problems + 1))
            issues+=("$APP: re-sign command failed -- not expected to fail, worth a closer look rather than a routine Step 11 rebuild")
        elif ! codesign --verify --deep --strict "$bundle" >/dev/null 2>&1; then
            echo "[WARN] Local code-signature verification failed after re-sign"
            problems=$((problems + 1))
            issues+=("$APP: local code-signature verification failed after re-sign -- signer trust/notarization remains unestablished")
        elif codesign -dv "$bundle" 2>&1 | grep -q "not signed"; then
            echo "[WARN] Still unsigned after a re-sign attempt"
            problems=$((problems + 1))
            issues+=("$APP: still unsigned after a re-sign attempt -- not expected to fail, worth a closer look rather than a routine Step 11 rebuild")
        else
            echo "[OK]   Local ad-hoc signature verified (signer trust/notarization unestablished)"
        fi

        "$LSREGISTER" -f "$bundle" >/dev/null 2>&1 || true
        local suffix="${exe_name#uaro-}"
        if "$LSREGISTER" -dump 2>/dev/null | grep -q "identifier:.*com.uaro.$suffix"; then
            echo "[OK]   Registered with Launch Services"
        else
            echo "[WARN] Not showing up in Launch Services registration"
            problems=$((problems + 1))
            issues+=("$APP: not registered with Launch Services after lsregister -f -- not expected to fail, worth a closer look")
        fi
    done

    echo "----------------------------------"
    # Required launcher absence is accumulated above; the final problems decision is authoritative.

    if [[ $problems -eq 0 ]]; then
        echo "All checks passed."
        exit 0
    fi

    echo "$problems issue(s) found that repair could not fully auto-fix:"
    for i in "${issues[@]}"; do
        echo "  - $i"
    done
    echo ""
    echo "Next step: open a Claude Code/Codex session in this repo (or paste the lines above into an existing one) and say:"
    echo "  \"uaro-cli repair found the issues above on my uaRO install -- fix them following SKILL.md's Step 11.\""
    echo "Exiting with status 1 so this is also detectable by anything scripting against uaro-cli, not just by reading this output."
    exit 1
}

case "$1" in
    kill)   cmd_kill ;;
    launch) cmd_launch ;;
    repair) cmd_repair ;;
    *)      usage ;;
esac
SCRIPT
chmod +x /opt/homebrew/bin/uaro-cli
```

**MANDATORY verification:**

```bash
zsh -n /opt/homebrew/bin/uaro-cli   # syntax check
command -v uaro-cli                 # should resolve to /opt/homebrew/bin/uaro-cli
uaro-cli                            # no args -> prints usage, doesn't error
uaro-cli kill                       # safe even with nothing running -- confirm it prints the "Killed..." line, not an error
uaro-cli repair; echo "exit: $?"      # safe/idempotent -- confirm every line reads [OK], ending in "All checks passed." and exit 0
```

**Prove `repair`'s diagnosis actually works, don't just trust a clean first run** — deliberately break something reversible, confirm `repair` both detects and fixes it, then confirm the underlying state is genuinely restored (not just repair's own say-so):

```bash
chmod -x "/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher"
uaro-cli repair; echo "exit: $?"
# Expect: "[FIXED] Executable bit was missing -- restored", ending in "All checks passed." and exit 0
test -x "/Applications/UaRO Patcher.app/Contents/MacOS/uaro-patcher" && echo "confirmed executable again"
```

**Also prove the *unfixable*-issue path — the exit code and the actionable next-step message, not just the auto-fix path above:**

```bash
cp "/Applications/UaRO Game.app/Contents/MacOS/uaro-game" /tmp/uaro-game.orig-backup
sed -i '' 's/command -v whisky/TEST_REMOVED/' "/Applications/UaRO Game.app/Contents/MacOS/uaro-game"
uaro-cli repair; echo "exit: $?"
# Expect: "[WARN] Predates the command -v whisky fallback fix...", a "1 issue(s) found" summary listing
# it by name, the "Next step: open a Claude Code/Codex session..." block, and exit 1 -- not 0.
cp /tmp/uaro-game.orig-backup "/Applications/UaRO Game.app/Contents/MacOS/uaro-game"   # restore immediately
chmod +x "/Applications/UaRO Game.app/Contents/MacOS/uaro-game"
uaro-cli repair; echo "exit: $?"   # confirm back to "All checks passed." / exit 0 before moving on
```

**Standing rule, same as the three launcher scripts:** if `BOTTLE_NAME`, `GAME_DIR`, or the set of process names killed on relaunch ever changes, update this script too — it's a fourth copy of that same logic, not exempt from the "keep all launcher-adjacent scripts in sync" rule in Step 11.

**Why this isn't a `~/.zshrc` alias/function instead** (a real suggestion from Discord contributor Rhya, considered and declined): a `~/.zshrc` edit is a global, unversioned mutation to a file this skill doesn't own and can't cleanly find-and-remove on uninstall, and it silently assumes the user's shell is `zsh` specifically. A standalone script dropped into an already-`PATH`'d directory gets the same one-word convenience (`uaro-cli kill`, not a full path) while staying a single file this skill can create, update, and delete cleanly — consistent with this project's existing preference for self-contained, reversible artifacts over editing shared user config.

## Phase E — Verify & wrap-up (Step 12)

The last checkpoint before calling the install done — confirm the launchers, patcher, and config round-trip all actually work together, then hand the user the wrap-up message.

## Step 12 — First-run verification (do this before considering the install done)

Do not call the installation complete until all three gates below pass for the same bottle and game directory:

| Gate | Required evidence |
|---|---|
| Target | Launcher bundles, `Info.plist`, game config, FCOM backup/byte diff, and the selected `GAME_DIR` all read back correctly |
| Execution | The launcher uses the resolved Whisky CLI, bottle, `WINEPREFIX`, DLL overrides, and runtime actually intended for this install |
| Behavior | Settings round-trip, the patcher advances past `Getting patch_main.txt...`, and the game reaches a stable login or equivalent user-visible success |

If only the target files pass, report `UNCONFIRMED`; a running process without readable runtime evidence is also `UNCONFIRMED`. If a gate cannot be tested because the user has not clicked through a GUI or logged in, stop at that gate instead of inferring success from the earlier steps.

### Execution-evidence procedure (F-03)

Keep the three gates separate. Record two different claims:

- **What the launcher says:** the literal bottle, game directory, runtime, WINEPREFIX, DLL overrides, and shell environment written into the launcher or manifest.
- **What actually executed:** independent readback of the resolved Whisky CLI, the runtime executable, WINEPREFIX, relevant environment, and (only when already safely observable) the live process executable and arguments.

Static/readback evidence may inspect the bottle literal, game directory, unresolved placeholders, Whisky CLI resolution, DLL overrides, shellenv, WINEPREFIX, the runtime executable, and wine64 --version. Do not launch a process merely to obtain evidence. If live execution cannot be independently proven, record EXECUTION = UNCONFIRMED.

Target = PASS does not imply Execution = PASS. Behavior = PASS does not imply Execution = PASS; a behavior claim cannot fill an execution-evidence gap.


1. Open `UaRO Settings.app`. Confirm it runs the FCOM re-patch without error, then opens "RO OpenSetup" with no crash. In its Resolution dropdown, pick the closest same-aspect-ratio entry to what the user actually wants (there is no guarantee the exact requested pixel value is offered). Click **Apply**, then **OK**.
2. Confirm the round-trip: `grep -E "WIDTH|HEIGHT|OLD_WIDTH|OLD_HEIGHT" "$GAME_DIR/savedata/OptionInfo.lua"` should now show the GUI's chosen values in `WIDTH`/`HEIGHT` and the previous values preserved in `OLD_WIDTH`/`OLD_HEIGHT`.
3. Open `UaRO Patcher.app`. Confirm the patcher window actually starts downloading/checking patches (progress bar moving, status line advancing past "Getting patch_main.txt...") rather than sitting stuck — if it's stuck, Step 9 (Gecko) did not actually take effect; redo it.
4. Tell the user: **never use the patcher's own in-app Settings button** — always use `UaRO Settings.app` for graphics/resolution changes, since the patcher will silently re-download an unpatched `setup.exe` over time.
5. Tell the user: **the game's `Alt` key is the Mac's `Option` (⌥) key** — the keyboard has no key actually labeled "Alt," and it's `Option`, not `Command`, that Step 9b maps to it. Any in-game shortcut described as `Alt+<letter>` (e.g. opening the item window) means physically pressing `Option+<letter>`.
6. Tell the user about `UaRO Game.app`: it's a faster relaunch option that skips the patcher's update check entirely — see the risk note in Step 11 and `TROUBLESHOOTING.md` before treating it as a full replacement for `UaRO Patcher.app`.
7. If built, tell the user about `uaro-cli`: `uaro-cli kill`/`uaro-cli launch`/`uaro-cli repair` from any Terminal window, no need to open Activity Monitor or redo the codesign/lsregister steps by hand.

## Installation complete — post this once Step 12 passes

This is the payoff moment after a long, mostly-invisible process — post it plainly, don't skip straight to a dry "done":

> [!TIP]
> **Setup complete — uaRO is fully installed and configured on this Mac.**
> Enjoy the game 🎮

Then walk the user through these four points, every time, regardless of how the install went:

1. **To play** — open `UaRO Patcher.app` in `/Applications` (Launchpad/Spotlight also work).
2. **To change any game setting** (resolution, graphics device, etc.) — always through `/Applications/UaRO Settings.app`. Never the patcher's own in-app Settings button — see item 4 above for why.
3. **A "Program Error" popup shouldn't appear anymore** — the launcher now silently retries once instead of showing it (see `TROUBLESHOOTING.md` for the underlying, still-not-root-caused bug this papers over). If it somehow still appears twice in a row, that's the retry also failing; don't panic, just relaunch `UaRO Patcher.app` manually.
4. **To uninstall uaRO entirely** — just invoke this skill again and ask for uninstall; the *Uninstall / rollback* section below has the exact commands, no need to figure it out manually.
5. **In-game menu shortcuts use `Option`, not `Command`** (e.g. `Option+A` for the item window) — this matches how uaRO behaves in a Windows VM too. Copy/paste (`Cmd+C`/`Cmd+V`) work normally, no change there.
6. **Switch to an English/ABC input source before playing** — if the Mac's active keyboard input method is Chinese, Japanese, Korean, Thai, or another non-ASCII input source, number-row hotkeys (`1`-`9`, Skill Bar/Hotkey Bar) won't register at all, and rebinding one will show "Unspecified value" instead. See `TROUBLESHOOTING.md` if English keeps silently reverting back specifically on the game window.
7. **`UaRO Game.app` skips the patcher — use it as a quick relaunch shortcut, not a permanent replacement.** It launches the game directly with no update check at all. Run `UaRO Patcher.app` at least once per session, or whenever a patch is known to have shipped, so this bottle actually gets it. See `TROUBLESHOOTING.md` for the unresolved risk this carries.
8. **If `uaro-cli` was built**, mention it's available from any Terminal window: `uaro-cli kill` to force-quit a stuck game/patcher, `uaro-cli launch` to start playing, `uaro-cli repair` to re-sign/re-register the launcher apps after a macOS update or manual edit — all three are shortcuts for things this skill otherwise does by hand.
9. **F1–F12 won't work as skill keys by default** — they'll trigger Mac's brightness/volume/Mission Control instead of your skills. Easiest fix: in the game's own Hotkey settings, shift your whole skill bar down one row — `F1`–`F12` → `1`–`9`, `1`–`9` → `Q`–`O`, `Q`–`O` → `A`–`L`. (Want to keep skills on the real F-keys instead? See `TROUBLESHOOTING.md`'s Input/Keyboard rows for the macOS/keyboard-firmware fix.)
10. **Want a mercenary or homunculus to auto-attack for you?** That's a separate, optional add-on (AzzyAI, third-party) — see *Optional: AzzyAI* right below for the install guide.

## Optional: AzzyAI (mercenary/homunculus auto-attack AI)

AzzyAI is a third-party Lua AI that can make a mercenary or homunculus automatically fight nearby monsters.

### What AzzyAI does

AzzyAI makes your **mercenary** or **homunculus** automatically fight nearby monsters.

- Searches about **12 cells** when you stand still, or **7 cells** while moving.
- By default, it may ignore monsters that stand still because they may be plants.
- The uaRO skill applies the compatibility fixes needed for it to detect and attack monsters correctly.

Would you like to install AzzyAI now? **Yes / No**

- **Yes** — read and follow [`AZZYAI_FIXES.md`](./AZZYAI_FIXES.md) from Step 1 through Step 10, stopping for the user's confirmation after each step as usual.
- **No** — leave AzzyAI uninstalled and finish the uaRO setup.

## Troubleshooting reference

**Known open issues** and the **Common Gotchas table** now live in [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) (split out at v0.19.0 to keep this file's always-loaded size down — see that file's own intro for how to use it). Consult it whenever a step's mandatory verification fails, or a symptom shows up that this step's own text doesn't explain — it's indexed by `Category` tag (`Crash/Patcher`, `Crash/Gameplay`, `Input/Keyboard`, `Installer/FCOM`, `Install/Homebrew`, `Install/Download`, `Install/Installer`, `Bottle/Config`, `Runtime/Wine`, `Config/Graphics`, `Launcher/Signing`, `Tooling/Environment`) so you can jump straight to the relevant rows.

## Uninstall / rollback

> [!TIP]
> **This section is explicitly supported as a standalone entry point in a brand-new session** (see README.md's "Updating an existing install" / uninstall flow) — unlike every step above, `$GAME_DIR` and `$BOTTLE_NAME` may never have been set at all in this conversation, not merely gone stale. Resolve them for real before the backup command below, e.g.:
> ```bash
> ls ~/Games                              # confirm the real game folder name
> GAME_DIR="$HOME/Games/UaRO World of Your Dream"   # the real path for this machine, not the default verbatim
> WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
> "$WHISKY" list                          # confirm the real bottle name
> BOTTLE_NAME="uaro"                       # the real name for this machine, not the default verbatim
> ```

**Non-regenerable: GAME_DIR/savedata/** (save data, character settings). Every deletion level must pass the deterministic external-backup transaction immediately before deletion. The backup destination must be outside GAME_DIR, not merely outside GAME_DIR/savedata.

**Stage 2.3 — deterministic savedata backup integration.** The source policy distinguishes a missing path from an existing empty directory. The bundled uaro.py backup savedata executor owns source classification, destination boundaries, copy status, and independent tree comparison. This shell block only resolves the explicit runtime and destination, validates structured evidence, and grants the deletion gate after the executor proves success.

```bash
set -e
GAME_DIR="${GAME_DIR:?Resolve the real game directory before continuing}"
AURO_REPO_ROOT="${AURO_REPO_ROOT:?Resolve this checkout before starting the backup transaction}"
PYTHON_RUNTIME="${PYTHON_RUNTIME:-$(command -v python3 || true)}"
[[ -n "$PYTHON_RUNTIME" && "$PYTHON_RUNTIME" = /* && -x "$PYTHON_RUNTIME" ]] || {
  echo "BLOCKED: an absolute executable Python runtime is required" >&2
  exit 1
}
AURO_EXECUTOR="$AURO_REPO_ROOT/scripts/uaro.py"
[[ -f "$AURO_EXECUTOR" ]] || {
  echo "BLOCKED: deterministic savedata executor is missing" >&2
  exit 1
}
SOURCE="$GAME_DIR/savedata"
BACKUP_ROOT="${BACKUP_ROOT:-$HOME/Games/uaRO-savedata-backups}"

if [[ -n "${BACKUP_DIR:-}" ]]; then
  case "$BACKUP_DIR" in
    /*) ;;
    *) BACKUP_DIR="$BACKUP_ROOT/$BACKUP_DIR" ;;
  esac
else
  BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)-$$"
  while [[ -e "$BACKUP_DIR" ]]; do
    BACKUP_DIR="$BACKUP_ROOT/$(date +%Y%m%d-%H%M%S)-$$-$RANDOM"
  done
fi
if [[ -e "$BACKUP_DIR" ]]; then
  echo "Backup destination already exists; refusing to merge or overwrite: $BACKUP_DIR" >&2
  exit 1
fi
BACKUP_TARGET="$BACKUP_DIR/savedata"

if ! BACKUP_JSON="$("$PYTHON_RUNTIME" "$AURO_EXECUTOR" backup savedata \
  --game-dir "$GAME_DIR" \
  --destination "$BACKUP_TARGET")"; then
  echo "BLOCKED: deterministic savedata backup executor failed" >&2
  exit 1
fi
if ! "$PYTHON_RUNTIME" - "$BACKUP_JSON" "$GAME_DIR" "$SOURCE" "$BACKUP_TARGET" <<'PYEOF'
import json
import os
import sys

try:
    payload = json.loads(sys.argv[1])
except Exception as exc:
    print(f"BLOCKED: malformed savedata backup evidence: {exc}", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(payload, dict):
    print("BLOCKED: savedata backup evidence is not an object", file=sys.stderr)
    raise SystemExit(1)
required = (
    "operation", "capability", "game_dir", "source", "destination", "source_state",
    "copy", "comparison", "backup_verified", "deletion_authority", "mutation", "result",
)
missing = [key for key in required if key not in payload]
if missing:
    print(f"BLOCKED: incomplete savedata backup evidence: missing {missing}", file=sys.stderr)
    raise SystemExit(1)
expected_game, expected_source, expected_destination = sys.argv[2:5]
for key, expected in (("game_dir", expected_game), ("source", expected_source), ("destination", expected_destination)):
    reported = payload.get(key)
    if not isinstance(reported, str) or os.path.realpath(os.path.abspath(reported)) != os.path.realpath(os.path.abspath(expected)):
        print(f"BLOCKED: savedata backup evidence named a different {key}", file=sys.stderr)
        raise SystemExit(1)
if payload["operation"] != "backup-savedata" or payload["capability"] != "REVERSIBLE_MUTATION":
    print("BLOCKED: savedata backup executor returned an unexpected operation", file=sys.stderr)
    raise SystemExit(1)
if payload["source_state"] not in ("empty", "populated"):
    print("BLOCKED: savedata source policy rejected the backup", file=sys.stderr)
    raise SystemExit(1)
copy_info = payload["copy"]
comparison = payload["comparison"]
if not isinstance(copy_info, dict) or copy_info.get("status") != "succeeded" or copy_info.get("success") is not True:
    print("BLOCKED: savedata copy evidence is not successful", file=sys.stderr)
    raise SystemExit(1)
if not isinstance(comparison, dict) or comparison.get("status") != "equal":
    print("BLOCKED: savedata source/destination comparison did not pass", file=sys.stderr)
    raise SystemExit(1)
if payload["backup_verified"] is not True or payload["mutation"] is not True or payload["result"] != "success":
    print("BLOCKED: savedata backup did not prove a verified mutation", file=sys.stderr)
    raise SystemExit(1)
if payload["deletion_authority"] is not False:
    print("BLOCKED: executor cannot grant deletion authority", file=sys.stderr)
    raise SystemExit(1)
print(json.dumps(payload, sort_keys=True))
PYEOF
then
  exit 1
fi

SAVEDATA_BACKUP_VERIFIED=1
echo "Savedata backup independently verified at $BACKUP_TARGET"
```

SAVEDATA_BACKUP_VERIFIED=1 is set only after the deterministic executor reports a successful copy and an equal source/destination comparison. Run this gate and the chosen deletion block in the same shell invocation. The Level 1 deletion block refuses to proceed unless that flag is present; never treat an earlier success message as deletion authority.

Everything else is safely re-derivable by re-running this skill. **Ask the user which level they actually want** — don't default to the deepest one:

| Level | Removes | Keeps | When to use |
|---|---|---|---|
| **1 — Game only** | Launcher apps, `$GAME_DIR` | Bottle, WhiskyWine runtime, Whisky.app, Homebrew, Rosetta | Redoing Steps 6–11 fresh (corrupted install, want a clean patch state) |
| **2 — + Bottle** | Level 1 + the `$BOTTLE_NAME` bottle | Whisky.app, WhiskyWine runtime, Homebrew, Rosetta | Bottle config got tangled, want Step 5 redone from scratch |
| **3 — + Whisky itself** | Level 2 + Whisky.app + the WhiskyWine runtime | Homebrew, Rosetta | Done with Wine gaming on this Mac entirely |
| **4 — + shared infra** | Level 3 + Homebrew + Rosetta | nothing | ⚠️ Only if nothing *else* on this Mac depends on Homebrew/Rosetta — check first, most machines have unrelated tools relying on both |

**Recovery-first deletion rule:** filesystem paths below use `trash`, so the user can recover an accidentally selected target from the Trash. Check that it is available before starting. If it is missing, stop and have the user remove the exact paths in Finder; do not substitute `rm -rf` or another permanent-delete command. `brew uninstall` and `softwareupdate --remove-rosetta` are separate package-manager/system operations at Levels 3–4; re-check their dependency warnings and scope before running them.

```bash
command -v trash >/dev/null || { echo "The 'trash' command is required for recoverable removal; stop and use Finder if it is unavailable"; exit 1; }
```

```bash
# --- Level 1: game only ---
if [[ "${SAVEDATA_BACKUP_VERIFIED:-0}" != 1 ]]; then
  echo "Verified savedata backup is required in this same shell before deletion"
  exit 1
fi
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
"$LSREGISTER" -u "/Applications/UaRO Patcher.app" "/Applications/UaRO Settings.app" "/Applications/UaRO Game.app" 2>/dev/null
for TARGET in \
  "/Applications/UaRO Patcher.app" \
  "/Applications/UaRO Settings.app" \
  "/Applications/UaRO Game.app" \
  "$GAME_DIR" \
  "/opt/homebrew/bin/uaro-cli" \
  "$HOME/Games/UaRO_Setup.zip" \
  "$HOME/Games/UaRO_Setup"; do
  [[ -e "$TARGET" ]] && trash "$TARGET"
done
# The installer ZIP/extraction directory are siblings of $GAME_DIR, not children;
# include them in Level 1 so a multi-GB download does not leak after uninstall.
# Verify: neither app should resolve, and the game dir should be gone
"$LSREGISTER" -dump 2>/dev/null | grep -c "com.uaro" ;# expect 0
test -d "$GAME_DIR" && echo "still there" || echo "removed"
command -v uaro-cli && echo "still there" || echo "removed"
test -e ~/Games/UaRO_Setup.zip -o -d ~/Games/UaRO_Setup && echo "installer leftovers still there" || echo "installer leftovers removed"

# --- Level 2: also drop the bottle ---
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
"$WHISKY" delete "$BOTTLE_NAME"   # or remove via Whisky.app GUI
"$WHISKY" list | grep -q "$BOTTLE_NAME" && echo "still there" || echo "removed"

# --- Level 3: also remove Whisky.app + the WhiskyWine runtime ---
for TARGET in \
  "/Applications/Whisky.app" \
  "$HOME/Applications/Whisky.app" \
  "$HOME/Library/Application Support/com.isaacmarovitz.Whisky"; do
  [[ -e "$TARGET" ]] && trash "$TARGET"
done
brew uninstall --cask whisky 2>/dev/null   # no-op if it was sideloaded, not brewed
command -v whisky || echo "whisky CLI gone"

# --- Level 4: also remove shared infra (confirm nothing else needs these first) ---
softwareupdate --remove-rosetta 2>/dev/null   # only if truly nothing else needs Rosetta
# Homebrew's own uninstall is interactive/destructive to *everything* it manages —
# don't script this blind; point the user at https://github.com/Homebrew/install#uninstall-homebrew
# and let them run it themselves if they're certain.
```

**If Level 3+ is chosen, tell the user explicitly before they proceed:** Whisky is unmaintained upstream and its Homebrew cask is deprecated, while the WhiskyWine/GPTK download endpoint is unavailable (see the "Why this exists" background). Re-installing later depends on the fixed 2.3.5 release identity and the archived copy saved to this repo's GitHub Release (`whisky-backup-2026-07-25` on `jirukouya/auRO-whisky-macOS-setup`, or wherever the user's own copy of that release lives). Confirm that backup still exists and passes the Whisky verifier before letting the user tear down their only working copy.

## Credits & Disclaimer

**Acknowledgments**
- The original step-by-step reference this skill was built from and hardened against real-world failures came from **@45rn0d3u5** on the uaRO Discord ([source document](https://docs.google.com/document/d/1ISi_iijWQuf5AeAh-ITtLYWm-My444x--d7rvQLiaL8/edit?tab=t.0)). This skill wouldn't exist without that groundwork — thank you.
- Thanks to **Isaac Marovitz**, creator of [Whisky](https://getwhisky.app/), the Wine wrapper this entire install path is built on. Whisky itself is no longer actively maintained (discontinued April 2025), but it's still the right tool for this job, and a fair amount of this skill exists specifically to keep it usable despite that.

**Disclaimer**
- This project is unofficial and not affiliated with, endorsed by, or supported by uaRO, Gravity Co., Whisky/Isaac Marovitz, or Apple.
- Provided as-is, with no warranty of any kind — use at your own risk. See `TROUBLESHOOTING.md` for what's already known to be imperfect.
- This skill only reads/writes files under the directories it creates or is told to use (`$GAME_DIR`, the Whisky bottle, `/Applications/UaRO*.app`) plus standard Homebrew/system locations needed to install its own dependencies. It does not collect, transmit, or store any personal data, credentials, or telemetry — every credential prompt along the way (macOS admin password, uaRO account login) is handled directly by the user, never by this skill or the AI running it.
- Licensed under the [MIT License](./LICENSE) — see that file for the full text.
