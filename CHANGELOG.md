# Changelog

All notable changes to this skill are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). Versioning follows [Semantic Versioning](https://semver.org/) in spirit — MINOR bumps for new fixes/behavior, PATCH bumps for wording/doc-only corrections. Since this repo ships a procedure, not an API, "breaking change" isn't really applicable; a 1.0.0 will mark the install process being considered fully stable (no known open issues left).

## [Unreleased]

## [0.20.0] - 2026-08-20

### Added
- `AZZYAI_FIXES.md` gained a full "Installing AzzyAI" section — this repo previously only covered fixing AzzyAI once already installed, never how to get it onto a fresh uaRO install in the first place (download source, exact file placement, in-game activation, verification).
  - Verified download source: [github.com/SpenceKonde/AzzyAI](https://github.com/SpenceKonde/AzzyAI) (author's own repo, no packaged Releases — the zip archive is the real download).
  - `SKILL.md` now points at this from a new "Optional: AzzyAI" section and an *Installation complete* walkthrough item, instead of AzzyAI being entirely undiscoverable from the main install flow.
  - Companion Claude Code skill `azzyai-uaro-fix` updated to match (install flow + routing between "fresh install" and "already installed, won't attack").

## [0.19.2] - 2026-08-20

### Fixed
- Found by a fresh-session cold read of the v0.19.0 restructuring: Step 9b's `EditMenu` cleanup ran before its own stated "bottle must be closed first" precondition check; Phase C's header omitted Step 9b from its own step range; TROUBLESHOOTING.md's category list was missing `Crash/Patcher` (used only in Known open issues, not the table); the TOC didn't explain why `1a` precedes `1`. All four fixed — reordering, one added tag, one clarifying sentence, no behavior changes.

## [0.19.1] - 2026-08-20

### Added
- F1-F12 skill-key gotcha (Installation complete item 9 + `TROUBLESHOOTING.md`) now leads with a simpler fix: remap the game's own hotkey bar down one keyboard row instead of fighting macOS/keyboard-firmware F-row settings — prompted by a Discord player report (MrStealYoGirl) that skills were unusable via mouse-only.

## [0.19.0] - 2026-08-20

### Changed
- Restructured for scannability: `SKILL.md` gained a Quick Routing table and 5 navigational Phase headers (A–E) grouping the existing Steps 1–12, and a condensed "5 rules" callout at the top of Section 0.
  - Known Open Issues and the Common Gotchas table moved to a new `TROUBLESHOOTING.md` — pure lookup-on-symptom content, never needed for a normal successful install.
  - `CLAUDE.md`'s standing single-file constraint updated to describe this two-file model.

## [0.18.0] - 2026-08-01

### Fixed
- Found during the first full live run of this skill by an external user (fresh Apple Silicon Mac, macOS 26.5.2), at Step 12's first-run verification — not by a cold-read:
  - **`uaro-settings` (Step 11) silently did nothing when double-clicked whenever `setup.exe` was already FCOM-patched — which is the normal healthy state after Step 8.** Under `set -e`, `_patch_setup_exe`'s final `[[ "$b_cur" == "dcd8dfe0" ]] && ...` Site-B check returns 1 when the file is already patched; that becomes the function's exit status, and `errexit` kills the script before the `exec wine64 "setup.exe"` line ever runs. This is the same `set -e` failure class as `uaro-patcher`'s `wait` bug fixed in 0.16.0 — that sweep verified the patcher script end to end but didn't re-audit the settings script for siblings. The bug never fires while `setup.exe` still *needs* patching (the `dd` runs and returns 0), which is why the original field test — run right after a fresh unpatched state — missed it. Reproduced in isolation (`zsh -c 'set -e; f() { [[ a == b ]] && echo x; }; f; echo reached'` never prints "reached"), then confirmed live: adding `return 0` as `_patch_setup_exe`'s last line fixed the launcher immediately on the affected machine. `uaro-patcher` and `uaro-game` are confirmed unaffected (they define no shell functions at all).
  - Step 2a gained a healing check for it (`grep -q 'return 0'` against the installed `uaro-settings`), and the Common Gotchas table a `Launcher/Signing` row, so pre-0.18.0 installs get offered the fix without waiting for the symptom to be reported.
  - **`uaro-patcher`'s crash-retry loop misread the patcher's own Launch Game handoff as the known early crash, spawning a ghost second patcher window alongside the launching game.** Probed live with an instrumented run: clicking Launch Game kills the patcher with exit 137 (SIGKILL) 44s after launch — a non-zero exit inside the sub-60s window, matching the retry heuristic's crash signature exactly (0.16.0's fix made the retry actually fire; this run was the first to see it fire on a *successful* handoff). The loop now checks whether `uaRO.exe` is running after the patcher exits — the script's own startup cleanup pkills any stale `uaRO.exe`, so a running one here was necessarily started by this session — and treats that as a successful handoff (exit 0, no retry). Step 2a gained a matching healing check and the gotchas table a row.

### Added
- **Fullscreen Cmd+Tab focus-bounce gotcha** (new `Config/Graphics` row), also from the same live run: with `ISFULLSCREENMODE=1`, tabbing away from the game then back in bounces focus straight back out every time — the game becomes unplayable until quit and relaunched. Second confirmed symptom of the fullscreen setting this skill already configures away (the black-screen row); the new row also warns that the client rewrites `OptionInfo.lua` on exit, so the flip back to `0` must happen with the game fully closed or it gets clobbered.
- **F1-F12 skill-key guidance** (new walkthrough item 9 in *Installation complete*, plus an `Input/Keyboard` gotcha row), from the same live run: RO leans on the F-row, but Mac keyboards default it to brightness/volume/media. Apple keyboards: the System Settings *"Use F1, F2, etc. keys as standard function keys"* toggle, or per-app via the optional [Fluor](https://github.com/Pyroh/Fluor) menu-bar app (`brew install --cask fluor`) — with two live-verified wrinkles: Fluor rules must be created *while the game is running and frontmost* (the frontmost app presents as the launcher's own bundle name, `UaRO Game`/`UaRO Patcher`, not a Wine process name), and one live test on macOS 26.5.2 saw a Fluor rule never engage (`fnState` never flipped), so the gotcha row includes a `defaults read -g com.apple.keyboard.fnState` verification probe. Third-party keyboards (Keychron etc.) decide F-row behavior in their own firmware — neither the macOS toggle nor Fluor can affect them; documented the keyboard-side fixes instead (Keychron `fn+X+L` held ~4s in Mac mode, or the Mac/Windows hardware switch — the latter verified live as working, with the Cmd/Option swap trade-off noted).

## [0.17.0] - 2026-07-30

### Fixed
- Prompted by Discord feedback ("Rhya"): Steps 3, 4, and 9 ran their install/download commands unconditionally instead of checking first whether the target already existed, causing noisy errors (Step 3), a hanging fallback mirror (Step 4), and a false "failure" read on an already-installed Gecko (Step 9).
  - Added check-first guards to all three steps, plus a general "check real end-state before installing" principle to Section 0.
  - Step 4: the archive.org fallback mirror is confirmed unreliable now (hangs on live test) — this repo's own mirror is tried first instead.

## [0.16.1] - 2026-07-29

### Changed
- `README.md`: Option A now lists per-app choices (Claude, ChatGPT, GitHub Copilot) in the same layout as Option B, adding [GitHub Copilot](https://github.com/features/ai/github-app) (macOS desktop app, free tier included) as a third choice.
  - Correction: Copilot CLI's "50 premium requests/month" figure (added earlier this same release, below) was stale — GitHub retired that billing model to legacy; current Free plan is "2,000 completions/month + limited chat/agent usage" per `docs.github.com/en/copilot/get-started/plans`, checked directly this time rather than reused from the earlier entry.
  - Also notes ChatGPT/Codex does have a free tier (previously implied only Copilot did), but flags it as too limited for an install this long, same as Claude's.
  - Follow-up simplification: both options' per-app notes reworded to one consistent `name — note` style (Option B's had parenthetical asides, Option A didn't), and Copilot's note dropped the "2,000 completions/month" specifics — a new user picking an app doesn't need the number, just "free tier covers it." Display name shortened from "GitHub Copilot app" to "GitHub Copilot" throughout.
  - Follow-up cold-read (fresh agent, zero context, playing a non-technical user deciding which app to download from the README alone) surfaced five more stumbles, all fixed: the intro's "written for Claude Code or OpenAI Codex" contradicted the Copilot recommendation two paragraphs later, so it now lists all three; "most likely to cover it" was a bare hedge with no stated fallback, so a line was added pointing at Step 2a's existing state-detection (switch tools mid-install and it resumes from your Mac's actual state, not chat history); Copilot's `features/ai/github-app` link doesn't read as an obvious download page like the other two apps' `/download` URLs, so its bullet now says "click **Download** on that page"; Option A step 2's "start a new session" for Copilot wasn't parallel to the named tabs for Claude/ChatGPT, so it now names the actual UI element (**+** next to **Sessions**); and "Terminal" was used but never defined, so Option A's intro now glosses it in passing (the black command-line window under Applications → Utilities).
  - Reversal: all free-tier/paid-plan framing removed. A second cold-read pass confirmed the free-vs-paid reasoning itself was sound, but on reflection it added a decision the reader doesn't need to make — all three tools can complete the install, so Option A and B now just list Claude, ChatGPT, and Copilot side by side with "pick whichever one you already have," no tier caveats attached to any of them.
  - Option B's `claude` and `codex` bullets now each get their own copy-pasteable install command, matching `copilot`'s (previously the only one with one). Verified both against their own docs first: Claude Code's is `curl -fsSL https://claude.ai/install.sh | bash` (`code.claude.com/docs/en/setup`), Codex CLI's is `curl -fsSL https://chatgpt.com/codex/install.sh | sh` (`github.com/openai/codex` README) — both turned out to already ship the same kind of dependency-free curl script as Copilot's, so all three now read the same way.
  - "Open Terminal anywhere" assumed the reader already knew what that meant. Replaced with two concrete ways to actually find it: the Spotlight shortcut (⌘ Cmd+Space, type `Terminal`, Return) and its real location (Finder → Applications → Utilities → Terminal).
  - Follow-up (third cold-read): removing all tier framing fixed the previous decision-paralysis complaint but created the opposite problem for a reader with none of the three already installed — "pick whichever one you already have" gives them nothing to go on. Added "No preference? Start with **ChatGPT**." as a one-line tiebreaker, without reintroducing any tier/quota language.
  - Dropped "click **Download** on that page" from the Copilot bullet — unnecessary once the tier caveats were gone, and it made that one bullet longer than the other two for no real reason.
- `README.md`: "The problem this solves" linked "Ragnarok Online" to its Wikipedia article instead of uaRO's own site. Now links `uaRO` itself to [uaro.net](https://uaro.net/) (verified live — matches the game's own name and default install folder used throughout `SKILL.md`), with the Wikipedia link dropped entirely rather than kept alongside it.
- Prompted by Discord feedback (uaRO player "Defectivve") on unclear prerequisites, Git/Xcode confusion, and a request for a gentler pace:
  - `README.md`: "How to actually run this" now offers two paths — desktop app (Claude's Code tab / ChatGPT's Codex tab, no Terminal) or Terminal/CLI — both noting a paid plan is required.
  - `README.md`: "Updating an existing install" now points back at either path above instead of assuming a session is already open.
  - `SKILL.md` Step 1: added a heads-up about macOS's own Command Line Developer Tools popup (git/Xcode), so it's explained before the user sees it, not after.
  - `SKILL.md` 1a: per-step approval prompt reworded to "take your time, and let me know when you're ready" instead of "proceed to Step N+1?".
  - `README.md`: Option B now shows the full paste-able command inline instead of "paste the same message as above" — "above" was ambiguous with two options on the page.
  - `README.md`: Option A's "pick any folder" (unexplained, per a cold-read agent flagging it as a genuine stumble) now gives a concrete default — pick Documents — and corrects the actual click order (Code/Codex tab first, *then* new chat, which is what triggers the folder picker) after checking both desktop apps directly.
  - `SKILL.md` Step 1: added an upfront one-line "why" before the install command — Homebrew is what installs Whisky itself later, and git/Xcode Command Line Tools come along as plumbing — instead of only explaining the popup reactively once it appears.
- Prompted by Discord feedback ("Rhya"): `README.md` Option B now also lists [GitHub Copilot CLI](https://github.com/features/copilot/cli) (`copilot`) alongside Claude Code and Codex CLI — it has a free tier, so it doesn't require the paid plan the other two do. The top-level paid-plan note now scopes to Claude/ChatGPT specifically instead of implying all three need payment.
  - Follow-up: Copilot CLI's own commonly-documented install methods (`npm install -g @github/copilot`, `brew install copilot-cli`) both require something a genuinely fresh Mac doesn't have yet (Node.js, Homebrew) — the same class of problem this whole 0.16.1 release exists to fix. Switched the inline mention to `curl -fsSL https://gh.io/copilot-install | bash`, GitHub's own dependency-free installer script, matching how Claude Code's and Codex CLI's own install methods already work here.
  - Visual cleanup: Option B's three CLI choices had collapsed into one dense run-on sentence, with the curl command embedded in prose instead of its own copy-pasteable code block, and the intro line above it still only mentioned `claude`/`codex`. Reformatted into a short sub-list (one tool per line, matching Option A's rhythm), gave the curl command its own fenced block, and updated the intro line to mention all three tools.
  - Correction: "free tier with weekly credits" was wrong — Copilot Free's allowance (50 premium requests, which Copilot CLI draws from) resets monthly, not weekly, per GitHub's own pricing page ("Your included allowance resets every month"). This was taken from Rhya's Discord message without cross-checking against GitHub's own docs first; fixed to state the actual monthly figure instead.

## [0.16.0] - 2026-07-28

### Fixed
- Prompted by an eighth fresh, zero-context cold-read of the public repo, run against the actual current `main` (`f3e53dd`, 0.15.0):
  - **`uaro-patcher`'s crash-retry loop (Step 11) never actually retried, because `set -e` + a bare `wait $pid` interact badly.** The script sets `set -e` at the top (needed elsewhere), then the retry loop does `wine64 "UaRo Patcher.exe" & pid=$!; wait $pid; code=$?`. With `errexit` active, `wait $pid` on a non-zero exit — exactly the known false-positive crash this loop exists to catch — triggers `errexit` itself: the script terminates right there, before `code=$?`, the `elapsed` calculation, or the retry `if` ever run. Confirmed directly: `zsh -c 'set -e; false & wait $!; echo reached'` never prints "reached". Because `ShowCrashDialog=0` is set unconditionally, separately, before the loop, this silent give-up looks externally identical to a successful retry (no popup, process gone cleanly) — which is almost certainly why the "Verified fix, not theoretical" field test in Step 11 didn't catch that the second `wine64` launch never actually happens. **Fixed by bracketing the `wait`/`code=$?` pair in `set +e`/`set -e`** so capturing a non-zero exit status doesn't itself trigger `errexit`. Verified end to end: extracted the actual script body from SKILL.md and ran it under real `/bin/zsh`, once simulating a crash-then-success (exits 0, confirming the retry actually fires) and once simulating both attempts crashing (exits with the crash code, confirming it still propagates correctly rather than being silently swallowed).
  - **Step 6's URL-download branch (`curl -fL ... "$INSTALLER_SOURCE"`) had no `caffeinate -i`**, unlike Step 4's WhiskyWine download, Step 7's installer run, and Step 9's Gecko install — despite being the same ~4.7GB installer fetched directly rather than staged via a browser. Wrapped it the same way, with the same justification.

## [0.15.0] - 2026-07-28

### Fixed
- Prompted by a seventh fresh, zero-context cold-read of the public repo, run against the actual current `main` (`8c741b8`, 0.14.0). Three minor findings, none blocking on the main execution path:
  - **The Common Gotchas table's "Inno Setup installs into the bottle" row (`Install/Installer`) had the one surviving bare, unquoted `whisky` call in the whole file** (`eval $(whisky shellenv <bottle>)`) — missed by every prior sweep because it lives in the reference table, not a numbered Step. Fixed to match the established pattern: `WHISKY=$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd); eval "$("$WHISKY" shellenv <bottle>)"`.
  - **Step 9's primary Gecko install (`winetricks -q gecko`) wasn't wrapped in `caffeinate -i`**, unlike every other unattended multi-minute operation in this file (Step 4's WhiskyWine download, Step 7's installer run) — both of which explain why. Wrapped it the same way, with the same justification.
  - **`$SETUP` (Step 8) was reused bare across two later, separately-fenced code blocks** (the `dd`/Python patch, and the mandatory byte-diff verification) with no inline re-derivation, unlike `$APPS`'s pattern in Step 11. Not a silent failure (missing `$SETUP` fails loudly via `cp`/`xxd`/`cmp` file-not-found), but inconsistent with the file's own standing re-derivation rule. Added `SETUP="$GAME_DIR/setup.exe"` at the top of both later blocks, plus a note after Step 8's opening block naming the rule explicitly. Verified all three Step 8 blocks — backup, patch, and verification — end to end as genuinely separate `/bin/bash` processes against a synthetic binary; the verification block's output matched the doc's own documented expected offsets exactly (`0x2C0CD`, `0x21E39`, `0x21E3B`, `0x21E3C`).

## [0.14.0] - 2026-07-28

### Fixed
- Prompted by a sixth fresh, zero-context cold-read of the public repo, run against the actual current `main` (`a6ea8a7`, 0.13.0). One real finding survived: **four more bare `whisky` calls, uncounted by the 0.13.0 fix, including one inside the very fix that shipped that version:**
  - **Section 2a's existing-bottle detection** (`whisky list 2>/dev/null`) — bare, so on a non-Homebrew Whisky install it silently reports nothing found (its own `2>/dev/null` swallows the error) instead of degrading to the fallback path.
  - **The Uninstall section's own re-derivation TIP** (`whisky list # confirm the real bottle name`) — bare. Notable because this exact block was added *this same version* to fix a different bug (missing `$GAME_DIR`/`$BOTTLE_NAME` re-derivation), and reintroduced this one in the process.
  - **Uninstall Level 2's bottle deletion** (`"$(command -v whisky)" delete "$BOTTLE_NAME"`) and the **verification line right after** (`whisky list | grep -q ...`) — the first had `command -v whisky` but no `|| echo .../WhiskyCmd` fallback; the second was fully bare. Worst-case site for this bug: Uninstall is documented as a standalone entry point with no earlier block that would already have resolved `$WHISKY`, so a non-brew install fails outright with "command not found" instead of deleting the bottle.
  - Fixed all four the same way as 0.13.0: resolve `WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"` first, then call `"$WHISKY" ...`. Verified by actually running all three reconstructed blocks under `/bin/bash` with `whisky` removed from `PATH` — all three now resolve to the fallback path correctly.

## [0.13.0] - 2026-07-28

### Fixed
- Prompted by a fifth fresh, zero-context cold-read of the public repo, run against the actual current `main` (`f0d8c0f`, 0.12.0) rather than a stale unpushed local state:
  - **Seven `eval "$(whisky shellenv "$BOTTLE_NAME")")` calls (Section 2a, Steps 5, 7, 9, and 9b) called bare `whisky` instead of resolving it via the `command -v whisky || echo .../WhiskyCmd` fallback used everywhere else in this file.** If Whisky was installed via Step 3's own documented GitHub-release fallback (no Homebrew symlink on PATH), all seven fail with `whisky: command not found`, silently breaking `WINEPREFIX`/`PATH` setup and cascading into `wine64`/`wineserver` "command not found" errors right after — the same bug class 0.4.0 already fixed, but only in the three launcher scripts, never here. Fixed by prepending `WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"` and calling `"$WHISKY" shellenv` at all seven sites.
  - **The Uninstall / rollback section never re-derived `$GAME_DIR`/`$BOTTLE_NAME`** before using them, unlike every install step above. This mattered more than ordinary staleness because README.md explicitly documents uninstall as something that can be the *only* thing run in a brand-new session — meaning these variables might never have been set at all, not merely gone stale. Added an explicit re-derivation TIP at the top of the section, before the savedata backup command that uses `$GAME_DIR` first.
  - **The Parameters-table TIP's `$GAME_DIR` line said the value was "decided at Step 1/2a"** — but `GAME_DIR` is decided in Section "1. Parameters," not "Step 1 — Homebrew" (unrelated), the exact ambiguous-numbering trap this file's own Table of Contents note warns against. Reworded to point at "Section 1 (Parameters)" explicitly, matching the wording already used correctly three lines away in Step 10.
  - **Section 2b's `CANDIDATE="<matched_file>"` placeholder had only a terse one-line comment**, unlike the heavily-worked `<UUID>`/`<GUID>`/`<CHOSEN_WIDTH>` placeholder examples elsewhere in this file. Not a silent failure (a literal run throws a loud `stat: No such file or directory`), but inconsistent with how carefully every other placeholder here is flagged. Expanded the comment to match the file's established placeholder-substitution style.

## [0.12.0] - 2026-07-28

### Fixed
- The remaining four findings from the same fourth cold-read as 0.11.0:
  - **Step 8's Python fallback (FCOM byte-patches) had no write-to-disk wrapper**, unlike Step 10's structurally identical script. Wrapped it in the same `cat > file <<'PYEOF' ... PYEOF` + `python3 file` pattern, verified against a synthetic binary with the exact pre-patch bytes at both offsets.
  - **General pattern: blocks in Steps 4 onward relied on the executor remembering whether `$BOTTLE_NAME`/`$GAME_DIR`/`$WHISKY` were still set, rather than just always re-deriving them.** The Parameters-table TIP callout already had the one-liners, but framed them as something to reach for *if* re-derivation is judged necessary — exactly the judgment call that goes wrong. Reworded as a standing instruction to prepend all three unconditionally to any block that touches them, since reassigning an already-correct value is a harmless no-op.
  - **That same TIP's `$GAME_DIR` line showed only the default value**, even though Step 7 explicitly instructs adopting a different real path if the installer redirected there — copying the TIP verbatim after that point would silently revert to the wrong directory. Reworded the comment to say so explicitly.
  - **Step 11's `Info.plist` was only shown in full for `UaRO Patcher.app`**, with `UaRO Settings.app`/`UaRO Game.app` given as a 4-column table to hand-mirror — precisely how a `CFBundleName` update misses its `CFBundleDisplayName` sibling. Replaced with a single loop over `$APPS` that generates all three via an unquoted heredoc (safe here — no backslash-heavy content, unlike the launcher scripts) with a `case` statement supplying the three per-bundle values. Verified under `/bin/bash` (3.2): all three plists generated with correct, distinct values, all pass `plutil -lint`.

## [0.11.0] - 2026-07-28

### Fixed
- Prompted by a fourth fresh, zero-context cold-read of the public repo — this one run *after* pushing, against the actual current `main`, so its findings were genuinely new rather than rediscoveries of already-fixed-but-unpublished work. Two of the three findings addressed here were regressions introduced by 0.10.0's own `$APPS` refactor:
  - **`$APPS` (Step 11) was reused across three widely-separated code blocks with no re-derivation guidance**, unlike every other reused variable in this file — Section 0's list never mentioned it. Confirmed the actual failure mode: in bash, an unset `$APPS` makes `for APP in "${APPS[@]}"` silently iterate zero times (no error), so the "MANDATORY" verification loop right after also silently produces no output — success by omission, while the launcher bundles are never actually `chmod +x`'d, signed, or registered. Fixed by having every block after the first re-derive `$APPS` from a real on-disk fact (`[[ -d "/Applications/UaRO Game.app" ]]`) instead of trying to remember a yes/no answer from several blocks back — added to Section 0's list, with a note recommending this "check something real" pattern generally over remembering decisions.
  - **`typeset -A EXE=(...)` (Step 11) is zsh/bash-4+ syntax inside a block fenced as plain ` ```bash `.** Confirmed macOS's actual `/bin/bash` is still 3.2.57, which rejects `-A` outright — under bash this made `${EXE[$APP]}` resolve to nothing, so `chmod +x ".../MacOS/"` (with the executable name dropped) silently succeeded against the directory instead of the binary, leaving every launcher non-executable. Replaced the associative array with an inline `case` statement (portable to both bash 3.2 and zsh), verified by actually running the reconstructed blocks under `/bin/bash` as separate processes (simulating real tool-call boundaries) for both the "build all three" and "decline Game.app" paths.
  - **`$GUID` (Step 10) was computed as a real shell variable, then the very next block required manually retyping it as literal placeholder text** inside a heredoc that has to stay quoted for an unrelated reason (protecting `OptionInfo.lua`'s backslash-heavy `DX9DEVICENAME` content) — get the retype wrong and the game ships with the literal string `<GUID_FROM_UUIDGEN>` instead of a real GUID. Fixed by passing `$GUID` through the environment (`GUID="$GUID" python3 ...`, read back via `os.environ["GUID"]`) instead of requiring a manual substitution, verified by actually running the env-var passthrough.

## [0.10.0] - 2026-07-28

### Fixed
- Prompted by a third fresh, zero-context cold-read of the public repo. Two of its six findings were genuine gaps (the other four had already been fixed locally in 0.9.0/0.9.1 but not yet pushed, so the agent — reading the stale published `main` — rediscovered already-solved problems):
  - **Declining `UaRO Game.app` in Step 11 required manually omitting it from ~8 separate hardcoded three-item lists** (the `mkdir` loop, icon-copy loop, `Info.plist` mirroring, chmod/plutil/`zsh -n`/codesign/backup-copy/`lsregister` commands, both verification loops) — a real chance of leaving a stray, half-built `Game.app` after the user explicitly declined it. Replaced every hardcoded list with a single `$APPS` array set once right after the consent question; every loop/command for the rest of Step 11 now reads `"${APPS[@]}"` instead of naming bundles literally, so there's exactly one place the decision is recorded. The three standalone per-bundle command blocks (chmod/plutil/`zsh -n`/codesign/backup-copy/`lsregister`) were also merged into one loop over `$APPS` using a `typeset -A EXE` map from bundle name to executable name, cutting ~15 near-duplicate lines down to one loop body. Verified by extracting the reconstructed blocks and running them under `zsh -n` and actual execution, for both the "build all three" and "decline Game.app" branches.
  - **`<CHOSEN_WIDTH>`/`<CHOSEN_HEIGHT>` in Step 10 had no shown derivation** from the `system_profiler SPDisplaysDataType | grep Resolution` output into two concrete integers — the Parameters table only described running the command, never parsing its output. Added the actual output format (`Resolution: 3456 x 2234 Retina`) and which two numbers to use to the `RESOLUTION` row, plus a matching worked example at Step 10's `<CHOSEN_WIDTH>`/`<CHOSEN_HEIGHT>` line itself.

## [0.9.1] - 2026-07-27

### Fixed
- Remaining findings from the same second cold-read pass as 0.9.0 (all doc-clarity, no behavior change):
  - **`UaRO_Setup.exe` (Step 6/7's installer) vs `setup.exe` (Step 8's FCOM-patch target, RO OpenSetup) were never explicitly distinguished**, despite the near-identical name — added a clarifying note at the top of Step 8.
  - **`UaRo Patcher.exe` (lowercase "o", the real on-disk filename)** reads like a typo on first encounter next to `UaRO Patcher.app` (capital "O", the launcher bundle). Added a note at its first mention (Step 9) spelling out all four similarly-named files (`UaRo Patcher.exe`, `UaRO Patcher.app`, `uaRO.exe`, `UaRO_Setup.exe`) and what each one actually is.
  - **Placeholder substitution (`<UUID>`, `<GUID_FROM_UUIDGEN>`, etc.) had no worked example** the first few times a reader actually has to do it. Added a concrete before/after example at Step 5's `<UUID>` substitution (the first place in the linear install this is required), and cross-referenced it from Step 10's script.

## [0.9.0] - 2026-07-27

### Fixed
- Prompted by a second fresh, zero-context cold-read of the public repo (post-0.8.1), specifically re-checking whether the previous round's fixes held and looking for anything new. The three most severe findings this round, all addressed:
  - **File-writing scripts shown as bare code fences with no write-to-disk command.** Step 10's `patch_optioninfo.py`, Step 11's `Info.plist` and all three launcher scripts (`uaro-patcher`/`uaro-settings`/`uaro-game`), and the `uaro-cli` helper were all printed as illustrative code blocks with no accompanying `cat > path <<'EOF'` wrapper actually creating the file — worse, the one place a heredoc *was* shown (`uaro-cli`'s install step) had a literal, never-resolved placeholder (`<paste the script above, with <BOTTLE_NAME>/<GAME_DIR> substituted>`) as its payload, which a literal run would write verbatim into `/opt/homebrew/bin/uaro-cli`, producing a broken file that still passes `chmod +x` and only fails at actual invocation. Every one of these is now a proper `cat > ... <<'DELIMITER'` block with the real content inline (merging the "here's what it looks like" and "now write it" steps into one, matching Step 4's existing `WhiskyWineVersion.plist` pattern) — verified by extracting each block, substituting placeholder values, and running the actual generated file/script through `zsh -n`, `plutil -lint`, or (for `OptionInfo.lua`'s `DX9DEVICENAME`) a raw byte-count check against the exact backslash pattern Step 10's own mandatory verification expects.
  - **`INSTALLER_SOURCE` was never actually assigned as a shell variable, and Section 2b's prose misdescribed which branch Step 6's code actually takes.** 2b said the relocated download makes "Step 6's branch take the `cp` path, not `curl`" — but the matching value (`~/Games/UaRO_Setup.zip`) actually hits Step 6's *first* `if` branch (a no-op, already staged), not the `cp` branch (which is for some other already-downloaded local path). Added an explicit `INSTALLER_SOURCE=...` assignment in both 2b and Step 6, and corrected the prose.
  - **Step 10's own script comment violated the numbering-scheme disambiguation note added in 0.8.0** — it said to pull a value from "Step 1's Parameters table," the exact "shared digit, different meaning" confusion that note exists to prevent (the Parameters table is in Section 1, not "Step 1 — Homebrew"). Reworded to avoid the ambiguous reference entirely.

## [0.8.1] - 2026-07-27

### Fixed
- Remaining cosmetic findings from the same cold-read pass as 0.8.0:
  - `README.md`'s "Latest: v0.2.0" line was five versions stale. Replaced with a pointer to `CHANGELOG.md` + `SKILL.md`'s own frontmatter version instead of a second hardcoded version summary — removes the duplication that let it go stale in the first place, rather than just updating the number again.
  - `README.md`'s Disclaimer still said "two apps in `/Applications`" from before `UaRO Game.app` and `uaro-cli` existed. Now says three apps, plus the optional `uaro-cli` helper in `/opt/homebrew/bin`.
  - `SKILL.md`'s "Installation complete" banner said "All 12 steps complete," undercounting the progress table's actual 15 tracked rows (Steps 1–12 plus 2a/2b/9b). Reworded to "Setup complete" instead of hardcoding a count that can drift again as steps are added.

## [0.8.0] - 2026-07-27

### Fixed
- Prompted by a fresh, zero-context cold-read of the public repo (a clean `git clone`, not a local read) done specifically to catch what a first-time executor with no prior context would actually trip on. Three findings addressed:
  - **Cross-block shell-variable persistence.** Section 0 only warned about angle-bracket placeholders baked into files written to disk — it never covered the separate risk of inline `$BOTTLE_NAME`/`$GAME_DIR`/`$WHISKY`/step-local variables (`$SETUP`, `$META`, `$GUID`, `$SUPPORT`, etc.) used directly in bash blocks, which many agent tool-execution harnesses do *not* keep set across separate tool calls (only cwd is guaranteed to persist). Added a new Section 0 principle plus a `[!TIP]` callout right after the Parameters table with copy-pasteable one-liners to re-derive the three most commonly reused values.
  - **`UaRO Game.app` consent gap on fresh installs.** Step 2a already required explicit user consent before retrofitting `UaRO Game.app` onto an *existing* install, but Step 11's actual build script built all three launchers unconditionally on a fresh install, with no equivalent checkpoint. Added the same consent question to the top of Step 11 itself, with explicit instructions to omit `UaRO Game.app` from every list in that step if declined.
  - **Colliding numbering schemes.** `1. Parameters`/`2. Pre-flight`/`2a`/`2b` (one-time setup/detection) and `Step 1`–`Step 12` (the install sequence) share overlapping bare digits — most visibly in the progress table, whose rows were labeled with bare `1`–`12` even though they mean `Step 1`–`Step 12`, not the similarly-numbered Parameters/Pre-flight sections. Relabeled those rows `Step N` explicitly, and added disambiguating notes at the Table of Contents and directly above the progress table.

## [0.7.0] - 2026-07-27

### Added
- `uaro-cli repair` now collects every issue it can't auto-fix into a numbered list and prints a ready-to-paste "next step" message pointing at Step 11 (e.g. *"uaro-cli repair found the issues above on my uaRO install -- fix them following SKILL.md's Step 11."*), instead of leaving the user to reread scattered `[WARN]` lines and figure out the next move themselves.
- `repair` now exits `1` when it found anything it couldn't fix, `0` otherwise — so the outcome is detectable by anything scripting against `uaro-cli`, not only by a human reading its output.
- New verification block demonstrating the *unfixable*-issue path specifically (not just the auto-fix path added in 0.6.0): deliberately strip the `command -v whisky` fallback from a real launcher script, confirm `repair` reports it, lists it by name in the summary, prints the actionable next-step message, and exits `1` — then restore the file and confirm a clean re-run exits `0`.

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
