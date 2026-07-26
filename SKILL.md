---
name: auro-whisky-macos-setup
description: Installs and configures uaRO (a Ragnarok Online private server) on macOS via Homebrew + Whisky + a manually-sourced WhiskyWine runtime — end to end on a fresh Mac. Covers Homebrew, Rosetta 2, Whisky.app, WhiskyWine runtime, bottle creation/config, downloading and running the uaRO installer, FCOM byte-patches for Rosetta compatibility, Wine Gecko pre-install, game config files, and building two launcher .app bundles. Trigger on "install uaRO on Mac", "set up uaRO with Whisky", "uaRO on a new Mac", "whisky uaro install", "uninstall uaRO", or whenever this file is handed to a fresh session on a brand-new machine with the instruction to just run it. Also covers uninstalling/removing an existing install (see the Uninstall / rollback section).
---

# uaRO on macOS via Whisky — Full Install Skill

This file is meant to be handed to a fresh Claude Code (or Codex) session on a brand-new Mac, with no other context. Read it once, then execute Steps 1–12 in order. Every value needed to actually do the work is inlined below — nothing here requires fetching an external reference doc first.

This is not a rewrite from theory. It is the corrected, verified procedure after actually running the whole thing once on a real machine (Apple Silicon, macOS 26.5.2) and finding several real bugs in the "obvious" version of these steps. Every mandatory verification step below exists because skipping it once actually produced a silent failure during that run — they are not defensive-programming boilerplate.

## 0. Operating principles — read before starting

- **Probe, don't assume, especially about what's "dead."** The premise "the Homebrew cask is disabled" turned out to be false on one real machine tested — it installed and worked fine. Try the normal path first every time; only fall back to a workaround if the normal path genuinely fails on *this* machine, right now.
- **A syntax-valid file is not a working file.** `plutil -lint` only checks that a plist parses as XML — it says nothing about whether the app that reads it can decode it into the shape it expects. Decode-test configs, don't just lint them.
- **A file existing right after you wrote it is not proof it will still be there in 30 seconds.** On a Mac with iCloud Drive "Desktop & Documents" sync enabled, files written under `~/Documents` *and* `~/Downloads` can be silently relocated into `~/Library/Mobile Documents/com~apple~CloudDocs/...` asynchronously, tens of seconds after creation — long after an immediate check would have reported "fine."
- **After any binary patch, byte-diff against a backup.** Don't trust that a patch did only what you intended — prove it with `cmp -l`.
- **`dd` writing to a binary file may be blocked in sandboxed/agent shells**, independent of file permissions. If it is, fall back to plain Python `open(path, 'r+b')` — it produces byte-identical results and isn't subject to the same restriction.
- **Never generate backslash-heavy config content through an unquoted heredoc** (`<< EOF`). Bash silently collapses `\\` pairs to `\` before the inner script even sees them. Always use a quoted delimiter (`<<'EOF'`) or write a real script file.
- **After every step, post the cumulative progress table (format below) and stop for explicit approval before touching the next step.** Never silently chain two steps together, even when a step "obviously" succeeded and even if the user seems to be in a hurry — this is the user's one visible checkpoint into a long, mostly-invisible process.
- **Angle-bracket placeholders (`<GAME_DIR>`, `<BOTTLE_NAME>`, `<UUID>`, `<CHOSEN_WIDTH>`, etc.) are not live shell variables — substitute the actual resolved value before writing them into anything that will execute standalone later** (the Python patch scripts, the two launcher `.app` scripts). This is different from an inline `$GAME_DIR` in a bash block meant to run immediately in this same shell. Code written to disk for later execution has no access to this session's variables — baking the literal text `<BOTTLE_NAME>` into a launcher script fails silently at write time and only breaks when the user actually double-clicks the app.
- **Some steps may trigger a macOS admin/login password prompt (`sudo`) — expected, not a sign of a hijacked machine.** Homebrew's installer (Step 1) commonly needs it the first time it creates `/opt/homebrew`; Rosetta (Step 2) occasionally does too. Warn the user *before* running that command that a password prompt may appear. If the shell running these commands has no interactive terminal attached, the prompt can't be answered programmatically at all — it will hang or fail outright (`sudo: a password is required`) instead of actually showing a box to type into. If that happens, tell the user to open a normal Terminal window themselves and run that one command directly — only they should ever type their own Mac password, never ask them to tell it to you.

## 1a. Progress table (post this, updated, after every single step)

Repost the **whole table**, not just the changed row, so the user always sees the full run at a glance:

| Step | What it does | Status | Notes |
|---|---|---|---|
| 2a | Detect existing state | ✅/❌/— | |
| 2b | Kick off installer download | ✅/❌/— | |
| 1 | Homebrew | ✅/❌/— | |
| 2 | Rosetta 2 (Apple Silicon only) | ✅/❌/—/N/A | |
| 3 | Whisky.app | ✅/❌/— | |
| 4 | WhiskyWine runtime | ✅/❌/— | |
| 5 | Bottle create/config | ✅/❌/— | |
| 6 | Download & extract installer | ✅/❌/— | |
| 7 | Run installer | ✅/❌/— | |
| 8 | FCOM byte-patches | ✅/❌/— | |
| 9 | Wine Gecko pre-install | ✅/❌/— | |
| 9b | Fix game menu shortcuts (Option=Alt) | ✅/❌/— | |
| 10 | Game config files | ✅/❌/— | |
| 11 | Launcher `.app` bundles + icon | ✅/❌/— | |
| 12 | First-run verification | ✅/❌/— | |

Rules for filling it in:
- **✅** — state *how* it was verified (the actual command/output checked), not just "done". E.g. "`wine64 --version` → `wine-7.7`", not "installed".
- **❌** — never leave this bare. The Notes cell must give exactly ONE recommended next action, chosen for *this* machine's actual detected environment (chip from `uname -m`, macOS version from `sw_vers`, what Pre-flight found already installed, what the real error text said) — not a generic list of possible causes. If genuinely unsure, say so plainly and propose the one action that would disambiguate it, rather than guessing.
- **—** — not attempted yet this run. Don't mark a step ❌ preemptively just because it's later in the sequence.
- **N/A** — doesn't apply to this machine (e.g. Step 2 on Intel Macs).
- After posting the table, stop and ask explicitly, e.g. *"Step N looks good — proceed to Step N+1?"* (or, on a ❌ row, *"Want me to apply the fix above before continuing?"*). Wait for the user's actual reply. Do not treat silence, a prior unrelated "yes," or your own confidence that it'll work as approval.

## 1. Parameters (decide these fresh, every machine)

| Parameter | Default | Notes |
|---|---|---|
| `BOTTLE_NAME` | `uaro` | Resolve the *real* on-disk UUID freshly via `whisky list` every time — never hardcode a UUID across machines. |
| `GAME_DIR` | `$HOME/Games/UaRO World of Your Dream` | Must NOT be under `~/Desktop`, `~/Documents`, or `~/Downloads` — see the iCloud gotcha below. `~/Games/<name>` or `~/Library/Application Support/<vendor>/<name>` are both confirmed-safe locations. |
| `RESOLUTION` | closest available in RO OpenSetup's dropdown | Do not hardcode a pixel value — RO OpenSetup (`setup.exe`) offers a fixed list of scaled resolutions derived from the actual display's native resolution/scale factor. **Detect this machine's actual display first** (`system_profiler SPDisplaysDataType \| grep Resolution`), then offer that as the recommended default when asking the user, rather than asking with no context. Pick the closest same-aspect-ratio entry from the real dropdown once you get to Step 12 — different Macs have different native/scaled resolution lists, so the "right" answer genuinely varies by machine. |
| `INSTALLER_SOURCE` | ask the user / check `~/Downloads` and common game folders, detected **by file size, not filename** (see 2b) | Could be a local `.zip` already downloaded, or a URL the user provides. Never guess/fabricate a download URL yourself. The installer itself sits behind a login wall (`https://uaro.net/cp/?module=account&action=login` — user-provided, not something you can fetch on their behalf), so this is always a human-driven download, never one you can script end-to-end. |

## 2. Pre-flight

```bash
sw_vers
uname -m                                  # arm64 = Apple Silicon, needs Rosetta (Step 2); anything else = Intel, see below
defaults read com.apple.finder FXICloudDriveDesktop FXICloudDriveDocuments 2>/dev/null
df -h /                                   # need roughly 15-20GB free — see below
```

**Check free disk space before going any further.** Between the uaRO installer itself (~4.7GB download, more once extracted), the WhiskyWine runtime, and the various `.orig-backup` copies this process keeps for safety, plan on needing roughly **15-20GB free** on the boot volume. If `df -h /` shows meaningfully less than that available, tell the user now, plainly — e.g. *"Heads up — this install needs about 15-20GB of free space, and this Mac currently has [X]GB available. Worth freeing up some space (Trash, old downloads, etc.) before we start, since running out partway through tends to show up as a confusing partial-download or partial-extraction failure rather than a clear error."* Don't let a low-space machine run silently into Step 6/7 and discover it there.

**Stop here if `uname -m` did not print `arm64`.** Whisky was built specifically for Apple Silicon — confirmed directly: the actual `Whisky.app` binary is Mach-O `arm64` only (no Intel slice), and Whisky's own Homebrew cask metadata declares `arch: arm64` as a requirement. Because of that, there isn't an Intel-compatible path through this particular skill. If this machine reports `x86_64` (or anything other than `arm64`), let the user know kindly before touching Step 1, e.g.: *"Quick heads-up — Whisky, the tool this install relies on, was built specifically for Apple Silicon Macs (M1 and later). This Mac has an Intel chip, so this particular skill isn't the right fit here."* Then hold off on Step 1 and the rest until the user's decided how they'd like to proceed.

**Also check the macOS version from `sw_vers` against Whisky's other stated requirement — macOS 14 (Sonoma) or newer.** This comes from the same cask metadata as the `arm64` requirement above (`{'macos': {'>=': ['14']}, 'arch': [...]}`), so it's just as real, even on an otherwise-compatible Apple Silicon Mac. If the version is older than 14, give the user the same kind of gentle heads-up before Step 1, e.g.: *"One more thing — Whisky officially needs macOS 14 (Sonoma) or newer, and this Mac is currently on [version]. Might be worth updating macOS first, if that's an option here."* Then pause for the user rather than pushing ahead into a cask install that may simply refuse to run.

The iCloud check above tells you if the *official* toggle is on. Treat a "1" as a strong warning. **Treat a missing/0 result as inconclusive, not as proof of safety** — `~/Downloads` was affected on a real machine despite not being one of the two officially-named folders. The only real safety net is the write-then-wait-then-recheck step in Step 6, not this probe.

## 2a. Detect existing state (before Step 3 — different machines start from different points)

Not every machine this runs on is a truly blank slate — Whisky, a bottle, or even a partial/full uaRO install may already exist from a previous attempt. Check before assuming Step 3 onward all need to run from zero:

```bash
# Existing Whisky.app / CLI?
ls -d /Applications/Whisky.app ~/Applications/Whisky.app 2>/dev/null
command -v whisky

# Existing bottles, and does any of them already have wine64?
whisky list 2>/dev/null

# Existing uaRO install anywhere plausible — common host paths, plus inside every bottle's drive_c
find ~/Games ~/Documents ~/Downloads ~/"Library/Application Support" -maxdepth 3 -iname "UaRO*" -type d 2>/dev/null
find ~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/*/drive_c -maxdepth 3 -iname "UaRO*" -type d 2>/dev/null
```

**If a bottle already exists, also check whether it's missing (or carrying an outdated version of) any fix added to this skill since it was created** — don't wait for the user to describe a symptom before mentioning it. Right now that means Step 9b's keybind fix; substitute the real bottle name for `$BOTTLE_NAME`:

```bash
eval "$(whisky shellenv "$BOTTLE_NAME")"
command -v wine64 >/dev/null || echo "runtime not linked yet — skip this check, Step 5 will sort it out"
EDITMENU=$(wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu 2>/dev/null)
OPTALT=$(wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt 2>/dev/null)
```

Two independent things to check here:

- **`$EDITMENU` has any output at all (even an empty value)** → this bottle has the *old*, superseded version of Step 9b applied (the one that disabled the hidden Edit menu). Tell the user plainly: *"Heads up — this uaRO install has an older fix applied that trades away native Cmd+V paste. There's a better fix now that doesn't have that trade-off. Want me to switch it over? Requires fully closing the game first."* If yes, apply the migration + current Step 9b.
- **`$OPTALT` is empty** → Step 9b (current version) was never applied at all. Tell the user plainly, even if they never mentioned a keybind problem: *"Heads up — this uaRO install was set up before a keybind fix was added to this skill. In-game menu shortcuts (like opening the item window) probably don't work correctly right now. Want me to apply that fix now? It's quick, but does require fully closing the game first."* Apply Step 9b if they say yes, then continue with whatever else this run was for.

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
CANDIDATE="<matched_file>"   # from the find command above
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

`INSTALLER_SOURCE` for Step 6 is now simply `~/Games/UaRO_Setup.zip` — a local path, so Step 6's branch takes the `cp` path, not `curl`.

## Step 1 — Homebrew

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || /usr/local/bin/brew shellenv)"
brew --version   # verify
```

**On a truly from-scratch Mac, that `eval` line is not optional.** The official installer does not add Homebrew to the *current* shell's `PATH` — it only prints instructions to add `brew shellenv` to a shell profile for *future* sessions. Skipping it means `brew --version` (and every later `brew` call this session) fails with "command not found" even though Step 1 actually succeeded — don't misread that as an install failure.

**Tell the user before running this:** the installer may prompt for the Mac's admin/login password (it needs it the first time to create `/opt/homebrew`). That's expected — not a sign of anything wrong. If the command instead hangs or fails with something like `sudo: a password is required` rather than actually showing a password prompt, the current shell has no interactive terminal attached to answer it — ask the user to open a normal Terminal window and run the install command there directly.

## Step 2 — Rosetta 2 (Apple Silicon only)

```bash
if [[ "$(uname -m)" == "arm64" ]] && ! pgrep -q oahd; then
  softwareupdate --install-rosetta --agree-to-license
fi
pgrep -q oahd && echo "Rosetta OK"
```

This can also prompt for the Mac's admin/login password on some machines — same guidance as Step 1: expected if it happens, and if it hangs/fails instead of prompting, have the user run it themselves in a normal Terminal window.

## Step 3 — Whisky.app

Try Homebrew first — **do not skip this attempt on the assumption the cask is disabled.** Verify the result yourself rather than trusting the exit code alone, since a disabled/no-op cask can still exit 0 while installing nothing.

```bash
brew install --cask whisky
ls -d /Applications/Whisky.app ~/Applications/Whisky.app 2>/dev/null
```

If neither path exists after that, fall back to the GitHub release:

```bash
curl -fL --progress-bar -o /tmp/Whisky.zip \
  https://github.com/Whisky-App/Whisky/releases/download/v2.3.5/Whisky.zip
ditto -xk /tmp/Whisky.zip /tmp/Whisky-extract
cp -R /tmp/Whisky-extract/Whisky.app /Applications/
xattr -dr com.apple.quarantine /Applications/Whisky.app 2>/dev/null || true
```

**If that download itself fails** (Whisky's own upstream `Whisky-App/Whisky` GitHub release is a single point of failure — Whisky is unmaintained upstream, so a vanished tag/asset is a real possibility, not paranoia): fall back to this repo's own archived copy instead of giving up. This repo is public, so plain `curl` works with no auth needed:

```bash
curl -fL --progress-bar -o /tmp/Whisky.zip \
  https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/Whisky-app-2.3.5.zip
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

Whisky's own downloader points at `data.getwhisky.app`, which is dead (confirm: `curl -I https://data.getwhisky.app/Libraries.zip` → 404). Fetch the Internet Archive snapshot instead — never rely on Whisky's own "Install GPTK" button, it shows a fake instant success and leaves an empty folder.

```bash
SUPPORT="$HOME/Library/Application Support/com.isaacmarovitz.Whisky"
mkdir -p ~/Downloads   # transient scratch only — the .zip itself isn't at risk the way an extracted app bundle is, but move fast
caffeinate -i curl -fL --progress-bar -o ~/Downloads/WhiskyWine-Libraries.zip \
  "https://web.archive.org/web/20240416174812id_/https://data.getwhisky.app/Libraries.zip"
```

**`caffeinate -i` wraps this download** — unlike a browser download (which requests its own "stay awake" assertion automatically), a `curl` call run this way has no such protection. On a laptop that's idle-timeout-eligible, this download can take a few minutes; without `caffeinate`, the Mac going to sleep partway through would stall or corrupt it, and it isn't obvious to a user why. `caffeinate` here just holds the system awake for exactly as long as `curl` is running, then releases automatically.

**If that archive.org snapshot itself becomes unreachable** (a single pinned snapshot URL is a real single point of failure, not a hypothetical — Internet Archive outages/URL changes do happen): fall back to this repo's own archived copy, byte-identical to the file above. This repo is public, so plain `curl` works with no auth needed:

```bash
caffeinate -i curl -fL --progress-bar -o ~/Downloads/WhiskyWine-Libraries.zip \
  https://github.com/jirukouya/auRO-whisky-macOS-setup/releases/download/whisky-backup-2026-07-25/WhiskyWine-Libraries-2.5.0.zip
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

## Step 5 — Create & configure the bottle

```bash
WHISKY="$(command -v whisky || echo /Applications/Whisky.app/Contents/Resources/WhiskyCmd)"
"$WHISKY" create "$BOTTLE_NAME"   # e.g. uaro
"$WHISKY" list                    # find the bottle, note its UUID (the *printed path* is cosmetically
                                   # wrong — it may show ~/Library/Containers/Whisky/... which doesn't
                                   # exist; the real path is always:
                                   # ~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/<UUID>)

META="$HOME/Library/Containers/com.isaacmarovitz.Whisky/Bottles/<UUID>/Metadata.plist"   # substitute the real UUID
plutil -replace dxvkConfig.dxvk           -bool true                                  "$META"
plutil -replace dxvkConfig.dxvkAsync      -bool true                                  "$META"
plutil -replace wineConfig.windowsVersion -string "win10"                             "$META"
plutil -replace wineConfig.enhancedSync   -xml '<dict><key>msync</key><dict/></dict>' "$META"
plutil -replace wineConfig.avxEnabled     -bool true                                  "$META"
plutil -lint "$META" && plutil -p "$META"
```

All five calls are safe to run unconditionally — they're idempotent, even though a fresh bottle typically already defaults `dxvkAsync`, `windowsVersion`, and `enhancedSync` correctly and only `dxvk`/`avxEnabled` actually need flipping. Confirm the printed result shows all five as intended before moving on.

**Self-healing check — confirm `wine64` is actually reachable through this bottle before trusting it, don't wait until Step 7's crash to find out:**

```bash
eval "$(whisky shellenv "$BOTTLE_NAME")"
command -v wine64 || echo "MISSING"
```

If that prints `MISSING` on a machine where Step 4 otherwise looked fine, the runtime and the bottle's environment aren't actually linked (seen on real machines where WhiskyWine was present on disk but a stale/mismatched `shellenv` path pointed elsewhere). Fix by re-running Step 4's install/verify, then re-check this before proceeding — don't proceed into Step 6/7 on a bottle where this printed `MISSING`.

## Step 6 — Download & extract the uaRO installer

`INSTALLER_SOURCE` resolves to either a URL or an already-downloaded local `.zip` path — branch on which one it actually is, don't hand a local path straight to `curl` (it doesn't reliably fetch bare local paths the way `cp` does). If 2b already relocated the download to `~/Games/UaRO_Setup.zip`, there's nothing to fetch — skip straight to extraction:

```bash
mkdir -p "$(dirname "$GAME_DIR")"   # e.g. ~/Games
if [[ "$INSTALLER_SOURCE" == ~/Games/UaRO_Setup.zip ]]; then
  : # already staged by 2b — nothing to do
elif [[ "$INSTALLER_SOURCE" =~ ^https?:// ]]; then
  curl -fL --progress-bar -o ~/Games/UaRO_Setup.zip "$INSTALLER_SOURCE"
else
  cp "$INSTALLER_SOURCE" ~/Games/UaRO_Setup.zip
fi
mkdir -p ~/Games/UaRO_Setup
ditto -xk ~/Games/UaRO_Setup.zip ~/Games/UaRO_Setup   # NEVER unzip — macOS's bundled Info-Zip
                                                       # silently no-ops on ZIP64 archives over 4GB
                                                       # (this installer is ~4.7GB): empty folder, no error.
```

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
eval "$(whisky shellenv "$BOTTLE_NAME")"
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

Rosetta can't translate certain alternate x87 FCOM instruction encodings; running them crashes `setup.exe` with "Unhandled illegal instruction." Both sites are context-checked before writing, so a build that doesn't need a given site skips it safely.

```bash
SETUP="$GAME_DIR/setup.exe"
cp "$SETUP" "$SETUP.orig-backup"
chmod u+w "$SETUP"
```

**Site A — 1 byte @ `0x2C0CD`, `dc`→`d8`.** Context window is 4 bytes *before* the patched byte, the byte itself, then 3 bytes after (`dc442410 dc d0dfe0`, patched byte in the middle) — reading 8 bytes forward *starting at* the offset will not match and looks like a false "uncatalogued build."

**Site B — 4 bytes @ `0x21E39`, `dcd8dfe0`→`ddd8b440`.** Context here *does* start exactly at the patch offset — the two sites use different alignment conventions, don't unify them.

Preferred method — plain `dd` (fine for normal unrestricted shells):

```bash
xxd -s $((0x2C0C9)) -l 8 "$SETUP"     # confirm context reads dc442410dcd0dfe0 before patching
printf '\xd8' | dd of="$SETUP" bs=1 seek=$((0x2C0CD)) count=1 conv=notrunc

xxd -s $((0x21E39)) -l 4 "$SETUP"     # confirm context reads dcd8dfe0 before patching
printf '\xdd\xd8\xb4\x40' | dd of="$SETUP" bs=1 seek=$((0x21E39)) count=4 conv=notrunc
```

**If `dd` writes are blocked** (some sandboxed/agent execution environments deny direct binary writes independent of file permissions), use this Python fallback — verified to produce byte-identical results. **`<GAME_DIR>` here is a placeholder, not a live shell variable — substitute the real resolved path before running this:**

```python
path = "<GAME_DIR>/setup.exe"
with open(path, "r+b") as f:
    f.seek(0x2C0CD); assert f.read(1) == b'\xdc'; f.seek(0x2C0CD); f.write(b'\xd8')
    f.seek(0x21E39); assert f.read(4) == bytes.fromhex("dcd8dfe0"); f.seek(0x21E39); f.write(bytes.fromhex("ddd8b440"))
```

**MANDATORY verification — byte-diff against the backup, don't just trust the write succeeded:**

```bash
cmp -l "$SETUP.orig-backup" "$SETUP" | awk '{printf "offset(dec)=%d 0x%X\n", $1-1, $1-1}'
# Expect exactly: 0x2C0CD, and within 0x21E39-0x21E3C (3 of the 4 bytes actually differ — the
# 2nd byte of Site B, 0xd8, is unchanged between pre/post). Nothing else should be listed.
ls -la "$SETUP" "$SETUP.orig-backup"   # sizes must match exactly
```

**If setup.exe crashes at a different `0042xxxx` address:** subtract the PE ImageBase `0x400000` to get the file offset. `0x0042C0CD` → Site A, `0x00421E39` → Site B. Any other address is an uncatalogued third site from a newer installer build — dump 16 bytes around it (`xxd -s $((0xOFFSET - 8)) -l 16 setup.exe`) and treat it as a new finding, don't assume the two offsets above are permanent across future uaRO releases.

## Step 9 — Pre-install Wine Gecko (mandatory, before `UaRO.app` is ever launched)

Do this right after Step 8, before the patcher is run for the first time. **This is a hard functional dependency, not a cosmetic prompt.** `UaRo Patcher.exe`'s initial patch-check runs through an embedded HTML/browser control — without Gecko it sits stuck at "Getting patch_main.txt..." forever, with a blank white panel and a progress bar that never moves.

There's a second, more important reason to do this ahead of time: the native "Wine Gecko Installer" dialog (source: `dl.winehq.org` — legitimate and currently working, unrelated to the dead `data.getwhisky.app` endpoint used elsewhere in this process) appears to show only **once**. Clicking **Cancel** instead of **Install** seems to make Wine remember that decision and never show the prompt again — leaving the patcher permanently stuck with no further recovery path short of manually re-triggering a Gecko install. Pre-installing removes this one-way door entirely.

**Primary method — non-interactive:**

```bash
brew install winetricks   # if not already present
eval "$(whisky shellenv "$BOTTLE_NAME")"
env | grep -i '^WINE'     # confirm WINEPREFIX actually points at the right bottle before proceeding
winetricks -q gecko
```

**Fallback, if winetricks isn't available or targets the wrong prefix — launch the patcher once on purpose and handle the prompt live:**

```bash
eval "$(whisky shellenv "$BOTTLE_NAME")"
nohup wine64 "$GAME_DIR/UaRo Patcher.exe" >/tmp/uaro_patcher_gecko.log 2>&1 &
disown
```

**Background this one too, same reasoning as Step 7** — it waits on a human clicking a dialog, which can take longer than your tooling's command-execution timeout allows. Don't block on it; tell the user to watch for the dialog, then come back and check.

**Same window-focus caveat as Step 7 applies here too** — this dialog may not automatically pop to the front. Tell the user to check the Dock (or Cmd+Tab) if it doesn't appear right away, rather than assuming nothing happened.

When the "Wine Gecko Installer" dialog appears, **click Install** and wait for it to finish. **Never click Cancel.** (If driving this via computer-use/screen automation rather than a human at the keyboard: some Wine dialog windows don't reliably show up in screenshot/click pipelines gated by per-app permission allowlists even when the parent app is granted access — if a click can't be confirmed to land correctly, ask the human to click it directly rather than guessing coordinates.)

**MANDATORY verification, either path:** relaunch the patcher and confirm the status line advances past "Getting patch_main.txt..." and the panel actually renders/starts downloading. A blank panel still stuck on that line after a "successful" Gecko install means this step did not actually succeed — redo it before continuing.

If the patcher then crashes right after Gecko finishes with a `Program Error` dialog, that's a separate, already-known open issue (see below) — Gecko itself installed correctly at that point; don't re-attempt this step because of that crash.

## Step 10 — Write game config files

### `dinput.ini` (ROExt plugin) — at `$GAME_DIR/dinput.ini`

The installer already writes most of this correctly; only `WindowLock` typically needs flipping. Back up first, then patch just that key (don't regenerate the whole file blind — the installer's copy has useful comments):

```bash
cp "$GAME_DIR/dinput.ini" "$GAME_DIR/dinput.ini.orig-backup"
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
cp "$GAME_DIR/savedata/OptionInfo.lua" "$GAME_DIR/savedata/OptionInfo.lua.orig-backup"
GUID="{$(uuidgen | tr a-z A-Z)}"
```

Write a small Python script **to a file** (not a heredoc) to do the substitution reliably:

```python
# /tmp/patch_optioninfo.py
import re
path = "<GAME_DIR>/savedata/OptionInfo.lua"
guid = "<GUID_FROM_UUIDGEN>"
W, H = <CHOSEN_WIDTH>, <CHOSEN_HEIGHT>   # first-pass guess only — use the RESOLUTION parameter's auto-detected
                                          # native-display value from Step 1's Parameters table; Step 12 will
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
```

```bash
python3 /tmp/patch_optioninfo.py
```

**MANDATORY verification — don't eyeball it with `cat`, count the actual bytes:**

```bash
grep -n "DX9DEVICENAME" "$GAME_DIR/savedata/OptionInfo.lua"
# Raw line must read exactly:  OptionInfoList["DX9DEVICENAME"] = "\\\\.\\DISPLAY1"
# (4 backslashes, dot, 2 backslashes — count them character by character, grep/cat print raw bytes here)
python3 -c "print(repr(open('$GAME_DIR/savedata/OptionInfo.lua','rb').read()))" | grep -o 'DX9DEVICENAME[^,]*'
```

**Width/height set here are provisional.** RO OpenSetup's own GUI is the authoritative writer for resolution (its dropdown only offers a fixed list of scaled values tied to the real display, and hand-edited values here won't necessarily match what it shows). Treat the values above as a reasonable starting guess; Step 12 will overwrite them correctly via the app's own Apply flow.

## Step 11 — Build the two launcher .app bundles

`UaRO.app` runs the patcher for daily play. `UaRO Settings.app` re-patches `setup.exe` then runs it, for graphics config — **players must never use the patcher's own in-app "Settings" button**, since `UaRo Patcher.exe` re-downloads any file whose hash mismatches its manifest, including the patched `setup.exe`, and the patcher's own Settings button runs the (by-then-unpatched) file directly.

```bash
for APP in "UaRO.app" "UaRO Settings.app"; do
  mkdir -p "/Applications/$APP/Contents/MacOS"
done
```

`Info.plist` (parameterize `name`/`identifier`/`executable` per bundle — shown for `UaRO.app`; mirror for `UaRO Settings.app` with `CFBundleName=UaRO Settings`, `CFBundleIdentifier=com.uaro.settings`, `CFBundleExecutable=uaro-settings`):

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
	<key>CFBundleName</key><string>UaRO</string>
	<key>CFBundleDisplayName</key><string>UaRO</string>
	<key>CFBundleIdentifier</key><string>com.uaro.launcher</string>
	<key>CFBundleVersion</key><string>1.0</string>
	<key>CFBundleShortVersionString</key><string>1.0</string>
	<key>CFBundlePackageType</key><string>APPL</string>
	<key>CFBundleIconFile</key><string>AppIcon.icns</string>
	<key>CFBundleExecutable</key><string>uaro-launch</string>
	<key>LSMinimumSystemVersion</key><string>11.0</string>
	<key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
```

Without `CFBundleIconFile` (and a matching icon actually placed in `Contents/Resources/`), both apps silently fall back to the generic blank-document icon — easy to miss since nothing errors, it just looks unfinished in Launchpad/Dock.

`UaRO.app/Contents/MacOS/uaro-launch` — **`<BOTTLE_NAME>` and `<GAME_DIR>` must be substituted with this machine's real resolved values before this file is written to disk; the app has no shell variables to fall back on when the user later double-clicks it:**

```bash
#!/bin/zsh
set -e
eval "$(/opt/homebrew/bin/whisky shellenv <BOTTLE_NAME>)"
cd "<GAME_DIR>"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:+$WINEDLLOVERRIDES;}msvcp140,vcruntime140,concrt140,vccorlib140=n,b"
export WINE_CPU_TOPOLOGY=4:0,1,2,3
exec wine64 "UaRo Patcher.exe" >/dev/null 2>&1
```

`WINEDLLOVERRIDES` **must append**, never replace — `whisky shellenv` already exports DXVK overrides (`dxgi,d3d9,d3d10core,d3d11=n,b`); overwriting the variable disables DXVK and tanks FPS. `WINE_CPU_TOPOLOGY=4:0,1,2,3` stabilizes Gepard Shield's anti-debug CPU-detection routines (fixes crashes ~3s after login and `Gepard::T Code: 3::110::12` disconnects).

`UaRO Settings.app/Contents/MacOS/uaro-settings` — same header, plus an idempotent re-patch of both FCOM sites (checks against the *post*-patch bytes so it skips cleanly if already done) before exec'ing `setup.exe`:

```bash
#!/bin/zsh
set -e
eval "$(/opt/homebrew/bin/whisky shellenv <BOTTLE_NAME>)"
cd "<GAME_DIR>"
export WINEDLLOVERRIDES="${WINEDLLOVERRIDES:+$WINEDLLOVERRIDES;}msvcp140,vcruntime140,concrt140,vccorlib140=n,b"
export WINE_CPU_TOPOLOGY=4:0,1,2,3

_patch_setup_exe() {
	local setup="$PWD/setup.exe"
	[[ -f "$setup" ]] || return 0
	chmod u+w "$setup" 2>/dev/null || true
	local a_cur=$(dd if="$setup" bs=1 skip=$((0x2C0CD)) count=1 2>/dev/null | xxd -p)
	[[ "$a_cur" == "dc" ]] && printf '\xd8' | dd of="$setup" bs=1 seek=$((0x2C0CD)) count=1 conv=notrunc 2>/dev/null
	local b_cur=$(dd if="$setup" bs=1 skip=$((0x21E39)) count=4 2>/dev/null | xxd -p)
	[[ "$b_cur" == "dcd8dfe0" ]] && printf '\xdd\xd8\xb4\x40' | dd of="$setup" bs=1 seek=$((0x21E39)) count=4 conv=notrunc 2>/dev/null
}

_patch_setup_exe
exec wine64 "setup.exe" >/dev/null 2>&1
```

### App icon (extract from the game's own files — do not fabricate/download one)

The game already ships a usable icon; the two launcher `.app`s just need it pulled out and converted. Requires `icoutils` (`brew install icoutils`, gives `wrestool`/`icotool`):

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

for APP in "UaRO.app" "UaRO Settings.app"; do
	mkdir -p "/Applications/$APP/Contents/Resources"
	cp AppIcon.icns "/Applications/$APP/Contents/Resources/AppIcon.icns"
done
```

The source PNG is only 48×48 (nothing higher-res is embedded anywhere in the game files), so `sips` is upscaling for the 256/512/1024 tiers — it'll look a little soft at the largest Launchpad/Finder preview sizes, but is fine for a desktop shortcut. This step can run any time after `$GAME_DIR` is populated (Step 6 onward) and before the final `lsregister -f` below, since that call is what makes Launch Services notice the new icon — if the two apps were already registered without an icon, re-run `lsregister -f` plus `killall Dock; killall Finder` to bust the icon cache after adding it later.

```bash
chmod +x "/Applications/UaRO.app/Contents/MacOS/uaro-launch" "/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings"
plutil -lint "/Applications/UaRO.app/Contents/Info.plist" "/Applications/UaRO Settings.app/Contents/Info.plist"
zsh -n "/Applications/UaRO.app/Contents/MacOS/uaro-launch"
zsh -n "/Applications/UaRO Settings.app/Contents/MacOS/uaro-settings"

# Backup copies inside the game folder, per the original design intent
cp -R "/Applications/UaRO.app" "$GAME_DIR/UaRO.app"
cp -R "/Applications/UaRO Settings.app" "$GAME_DIR/UaRO Settings.app"

LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
"$LSREGISTER" -f "/Applications/UaRO.app"
"$LSREGISTER" -f "/Applications/UaRO Settings.app"
```

**MANDATORY registration verification — never `mdls`/`mdfind`, Spotlight lags well behind actual registration and will falsely report nothing for a while:**

```bash
"$LSREGISTER" -dump 2>/dev/null | grep -A2 "identifier:.*com.uaro"
```

## Step 12 — First-run verification (do this before considering the install done)

1. Open `UaRO Settings.app`. Confirm it runs the FCOM re-patch without error, then opens "RO OpenSetup" with no crash. In its Resolution dropdown, pick the closest same-aspect-ratio entry to what the user actually wants (there is no guarantee the exact requested pixel value is offered). Click **Apply**, then **OK**.
2. Confirm the round-trip: `grep -E "WIDTH|HEIGHT|OLD_WIDTH|OLD_HEIGHT" "$GAME_DIR/savedata/OptionInfo.lua"` should now show the GUI's chosen values in `WIDTH`/`HEIGHT` and the previous values preserved in `OLD_WIDTH`/`OLD_HEIGHT`.
3. Open `UaRO.app`. Confirm the patcher window actually starts downloading/checking patches (progress bar moving, status line advancing past "Getting patch_main.txt...") rather than sitting stuck — if it's stuck, Step 9 (Gecko) did not actually take effect; redo it.
4. Tell the user: **never use the patcher's own in-app Settings button** — always use `UaRO Settings.app` for graphics/resolution changes, since the patcher will silently re-download an unpatched `setup.exe` over time.
5. Tell the user: **the game's `Alt` key is the Mac's `Option` (⌥) key** — the keyboard has no key actually labeled "Alt," and it's `Option`, not `Command`, that Step 9b maps to it. Any in-game shortcut described as `Alt+<letter>` (e.g. opening the item window) means physically pressing `Option+<letter>`.

## Installation complete — post this once Step 12 passes

This is the payoff moment after a long, mostly-invisible process — post it plainly, don't skip straight to a dry "done":

> [!TIP]
> **All 12 steps complete — uaRO is fully installed and configured on this Mac.**
> Enjoy the game 🎮

Then walk the user through these four points, every time, regardless of how the install went:

1. **To play** — open `UaRO.app` in `/Applications` (Launchpad/Spotlight also work).
2. **To change any game setting** (resolution, graphics device, etc.) — always through `/Applications/UaRO Settings.app`. Never the patcher's own in-app Settings button — see item 4 above for why.
3. **If a "Program Error" popup ever appears** — don't panic, this is a known unresolved Wine/Gecko crash (see *Known open issues* below), not something the user broke. Just click **Close** and relaunch `UaRO.app`; it has not reliably recurred on a second try.
4. **To uninstall uaRO entirely** — just invoke this skill again and ask for uninstall; the *Uninstall / rollback* section below has the exact commands, no need to figure it out manually.
5. **In-game menu shortcuts use `Option`, not `Command`** (e.g. `Option+A` for the item window) — this matches how uaRO behaves in a Windows VM too. Copy/paste (`Cmd+C`/`Cmd+V`) work normally, no change there.

## Known open issues

**Post-Gecko patcher crash (unresolved).** After Gecko finishes installing (Step 9) and the patcher begins downloading patch files, `UaRo Patcher.exe` crashed once with Wine's "Program Error" dialog:
```
0x0000014000a059 uaro patcher+0xa059: int  $3
```
`int $3` is the x86 breakpoint/trap instruction — normally caught by the process's own exception handler on real Windows (common in anti-debug checks and in Gecko's own Breakpad crash-reporting instrumentation) without visibly crashing. The loaded-module list at crash time included a cluster of Gecko/embedded-browser modules (`mozglue`, `nss3`, `lgpllibs`, `xul`, `ieframe`), suggesting the fault originates from Gecko being initialized/used by the patcher and that Wine isn't correctly delivering the trap to the guest's own handler.

**First mitigation:** just close the error and relaunch `UaRO.app` — this class of glitch has not reliably repeated on a second launch. If it does repeat consistently:
- Try `WINEDEBUG=+seh,+exception wine64 "UaRo Patcher.exe"` and capture what's actually thrown.
- Check Wine/Whisky issue trackers for Gecko + `int3`/breakpoint crash reports — embedded IE/Gecko browser controls are a known general weak spot under Wine.
- Investigate whether the patcher exposes a config flag to skip its HTML panel entirely, avoiding the Gecko-dependent code path (would need patcher-specific knowledge not yet gathered).

This is explicitly **not yet root-caused** — don't assume a future session solved it just because it isn't mentioned again here; check back with whoever's running it.

## Step 9b — Fix in-game menu shortcuts (Cmd+A/Cmd+Z-style) not registering

**Root cause, confirmed by reading Wine's actual source, not a guess:** the game's menu-style shortcuts (item window, etc.) are built for a Windows `Alt+<letter>` scheme. Wine's mac driver already translates a bare physical `Cmd` key into `Alt` by default (`winemac.drv/keyboard.c`, `kVK_Command → VK_LMENU` — no setting needed for that part) — but Whisky's forked Wine (`winemac.drv/cocoa_app.m`) *also* injects a hidden "Edit" menu (Cut/Copy/Paste/Select All/Undo) into every Wine window, bound to `Cmd+X/C/V/A/Z`. macOS matches that menu's key equivalents *before* a keypress ever reaches the game — so specifically `Cmd+A` (Select All) and `Cmd+Z` (Undo) get swallowed by that hidden menu and never reach the game as `Alt+A`/`Alt+Z`, while unrelated combos like `Cmd+Q`/`Cmd+E` (not in that menu) pass straight through untouched. Same bug, same symptom, already reported upstream: [Whisky-App/Whisky#1060](https://github.com/Whisky-App/Whisky/issues/1060).

**Don't fix this by disabling the hidden Edit menu (`EditMenu` registry key) — that was tried and tested for real, and it works, but it breaks something else.** Disabling that menu does stop it from swallowing `Cmd+A`/`Cmd+Z`, but that same hidden menu is *also* what makes `Cmd+C`/`Cmd+V` paste correctly in the first place (by silently converting them into the `Ctrl+C`/`Ctrl+V` the game actually expects) — so disabling it trades one broken shortcut for another. **The actual fix is to stop using `Cmd` for these shortcuts at all, and use `Option` instead** — `Option` was never part of that hidden menu's shortcut list, so it was never at risk of being swallowed to begin with, and this matches how uaRO already behaves for anyone who's played it in a Windows VM (VMware Fusion, etc.), where `Option`/`Alt` has always been the key that triggers these shortcuts.

**If this bottle previously had the old `EditMenu`-disable fix applied, undo it first** (check with `wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu` — any result at all, even empty, means it's set):

```bash
eval "$(whisky shellenv "$BOTTLE_NAME")"
wine64 reg delete 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu /f 2>/dev/null || true
```

**Do this after Step 9, before the patcher/game is ever launched for real play** — and any time this symptom is reported on an existing install. These settings are only read when a Wine window is created, so a fully closed game/bottle is required first:

```bash
pgrep -f "Wine/bin/wine64-preloader" >/dev/null && echo "uaRO/Wine still running — close it first, this fix needs a clean bottle" || echo "Clean, safe to proceed"
```

```bash
eval "$(whisky shellenv "$BOTTLE_NAME")"
wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt /t REG_SZ /d y /f
wine64 reg add 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v RightOptionIsAlt /t REG_SZ /d y /f
wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v LeftOptionIsAlt
wine64 reg query 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v RightOptionIsAlt
```

**Tell the user plainly, every time this is applied:** in-game menu shortcuts now use **`Option+<letter>`, not `Cmd+<letter>`** (matches the VMware/Windows-VM experience). `Cmd+C`/`Cmd+V`/`Cmd+X` keep working exactly as before for copy/paste — nothing changes there, and there's no trade-off this time.

**A community fork's alternate approach is not a substitute for this fix either.** [frankea/Whisky](https://github.com/frankea/Whisky) added a "Map Command Key to Windows Ctrl" toggle claiming to close #1060, but it only sets `LeftCommandIsCtrl`/`RightCommandIsCtrl` — a setting that controls how an *already-delivered* Cmd keypress gets translated. It does nothing about the hidden Edit menu swallowing `Cmd+A`/`Cmd+Z` before that translation ever happens (confirmed by reading that fork's actual commit diff — it never touches `EditMenu`), so it doesn't fix this symptom, and setting `LeftCommandIsAlt`/`RightCommandIsAlt` (sometimes suggested alongside it) does nothing at all — those registry names don't exist anywhere in Wine's source; Wine never reads them.

## Common Gotchas (reference table)

| Symptom | Cause | Fix |
|---|---|---|
| `brew install --cask whisky` exits 0 but installs nothing | Cask can be silently disabled upstream | Verify with `find_whisky_app`-equivalent check; fall back to GitHub release zip only if truly absent |
| `command not found: wine64` | WhiskyWine runtime never downloaded (dead CDN) | Manually install from Internet Archive snapshot (Step 4); never rely on Whisky's own downloader |
| Whisky's "Install GPTK" shows instant success but nothing works | Download URL 404s, Whisky doesn't surface the error | Ignore that button; install WhiskyWine manually |
| Empty folder after `unzip` | macOS's bundled unzip can't handle ZIP64 archives >4GB | Always use `ditto -xk` |
| `xattr -dr com.apple.quarantine` floods "Permission denied" | tar-extracted files are read-only; `xattr -d` needs write perms just to *attempt* a delete, regardless of whether the attribute exists | `chmod -R u+w ... \|\| true` before the `xattr` call, and `\|\| true` on it too |
| `WhiskyWineVersion.plist` written as a plain string silently fails `isWhiskyWineInstalled()` | Whisky's Codable decode expects a structured `{major,minor,patch,preRelease,build}` dict, not a string | Use the exact structured plist in Step 4 |
| `whisky list` prints a bottle path that doesn't exist | Cosmetic CLI display bug | Always use `~/Library/Containers/com.isaacmarovitz.Whisky/Bottles/<UUID>` |
| A just-extracted/downloaded file mysteriously vanishes and Wine reports `c0000135` | iCloud Drive silently relocated the folder out from under the running process — affects `~/Downloads` too, not just `~/Documents`/`~/Desktop` | Use a non-iCloud `GAME_DIR`/scratch dir (`~/Games/...`); always wait ~30s and recheck after any extraction there |
| Inno Setup installs into the bottle, not where `/DIR=` said | `whisky run` is App-sandboxed | Use `eval $(whisky shellenv <bottle>); wine64 setup.exe /DIR=Z:\...` directly |
| Game crashes ~3s after login | Gepard CPU detection | `WINE_CPU_TOPOLOGY=4:0,1,2,3` in the launcher |
| `Gepard::T Code: 3::110::12` | Native MSVC DLLs not loading | `WINEDLLOVERRIDES` must include `msvcp140,vcruntime140,concrt140,vccorlib140=n,b`, DLLs must sit next to the game exe |
| Low FPS / stutter | Launcher replaced `WINEDLLOVERRIDES` instead of appending | Use the `${VAR:+$VAR;}` append idiom, never overwrite |
| Cursor disappears over the game window | `MouseExclusive=1` | Set to `0` in `OptionInfo.lua` |
| Black screen on launch | `ISFULLSCREENMODE=1` | Set to `0` in `OptionInfo.lua` |
| `dd` write to a binary file silently denied | Some sandboxed/agent execution environments block direct `dd` writes independent of file permissions | Fall back to Python `open(path,'r+b')`, seek/write — byte-identical result |
| `DX9DEVICENAME` ends up with half the expected backslashes | Generated via an **unquoted** heredoc — the shell itself collapsed `\\` pairs before the inner script saw them | Use a quoted heredoc (`<<'EOF'`) or write a real script file, never an unquoted heredoc, for backslash-heavy content |
| Hand-edited resolution in `OptionInfo.lua` doesn't match what RO OpenSetup shows | `OptionInfo.lua` isn't the sole source of truth — RO OpenSetup has its own dropdown/writer | Pick the value from RO OpenSetup's own dropdown and click Apply; let it round-trip back into the file |
| A freshly built `.app` bundle doesn't show up via `mdls`/`mdfind` | Spotlight indexing lags well behind actual Launch Services registration | Verify with `lsregister -dump \| grep <bundle-id>` instead |
| Launcher `.app`s show the generic blank-document icon | No `CFBundleIconFile` + no icon actually placed in `Contents/Resources/` | Extract the game's own 48x48 icon from `UaRo Patcher.exe` (`wrestool`/`icotool`), build an `.icns` with `iconutil`, add `CFBundleIconFile`, then `lsregister -f` + `killall Dock; killall Finder` |
| `setup.exe` crashes 'illegal instruction at 0042C0CD' / '00421E39' | Untranslatable FCOM encodings at Site A / Site B | Run the FCOM patch (Step 8 / `UaRO Settings.app`) |
| `setup.exe` crashes at a *different* `0042xxxx` address | Uncatalogued third FCOM site (installer build changed) | Subtract `0x400000`, dump 16 bytes, treat as a new finding — don't assume the two known offsets are permanent |
| `setup.exe` "stops working" after a patcher update | `UaRo Patcher.exe` re-downloaded and overwrote the patched file with the original | Always use `UaRO Settings.app` (re-patches every launch); never the patcher's own in-app Settings button |
| Launcher errors "a bottle with that name does not exist" | Hardcoded bottle name doesn't match the real one | Resolve the actual bottle name/UUID dynamically, don't hardcode across machines |
| Patcher stuck forever at "Getting patch_main.txt...", blank white panel | Wine Gecko not installed — this is a hard dependency, not cosmetic | Pre-install via `winetricks -q gecko` (Step 9) before ever launching the patcher |
| Wine Gecko Installer prompt never reappears, patcher permanently stuck | Clicking **Cancel** instead of Install appears to make Wine remember the decision and never re-prompt | Always click **Install**; better yet, pre-install non-interactively so the prompt never appears live |
| `Cmd+A`/`Cmd+Z` (or other Alt-style menu shortcuts) do nothing in-game, but `Cmd+C`/`Cmd+V`/other Cmd-shortcuts work fine | Whisky's forked Wine injects a hidden Edit menu that intercepts `Cmd+A`/`Cmd+Z`/`Cmd+C`/`Cmd+X`/`Cmd+V` before the game ever sees them ([Whisky-App/Whisky#1060](https://github.com/Whisky-App/Whisky/issues/1060)) | Apply Step 9b: set `LeftOptionIsAlt`/`RightOptionIsAlt`, then use `Option+<letter>` in-game instead of `Cmd+<letter>` for menu shortcuts — leaves `Cmd+C`/`Cmd+V` untouched, no trade-off |
| In-game paste needs `Ctrl+V` instead of `Cmd+V` (on a bottle set up with an earlier version of this skill) | An earlier version of Step 9b fixed the above by disabling the hidden Edit menu entirely — which fixed `Cmd+A`/`Cmd+Z` but broke `Cmd+V`'s automatic paste as a side effect | Undo it: `wine64 reg delete 'HKEY_CURRENT_USER\Software\Wine\Mac Driver' /v EditMenu /f`, then apply the current Step 9b (`LeftOptionIsAlt`/`RightOptionIsAlt`) instead — fixes both with no trade-off |

## Uninstall / rollback

**Non-regenerable: `$GAME_DIR/savedata/`** (save data, character settings). Always back it up before removing anything, regardless of which level below is chosen:

```bash
cp -R "$GAME_DIR/savedata" ~/Desktop/uaRO-savedata-backup-"$(date +%Y%m%d)"
```

Everything else is safely re-derivable by re-running this skill. **Ask the user which level they actually want** — don't default to the deepest one:

| Level | Removes | Keeps | When to use |
|---|---|---|---|
| **1 — Game only** | Launcher apps, `$GAME_DIR` | Bottle, WhiskyWine runtime, Whisky.app, Homebrew, Rosetta | Redoing Steps 6–11 fresh (corrupted install, want a clean patch state) |
| **2 — + Bottle** | Level 1 + the `$BOTTLE_NAME` bottle | Whisky.app, WhiskyWine runtime, Homebrew, Rosetta | Bottle config got tangled, want Step 5 redone from scratch |
| **3 — + Whisky itself** | Level 2 + Whisky.app + the WhiskyWine runtime | Homebrew, Rosetta | Done with Wine gaming on this Mac entirely |
| **4 — + shared infra** | Level 3 + Homebrew + Rosetta | nothing | ⚠️ Only if nothing *else* on this Mac depends on Homebrew/Rosetta — check first, most machines have unrelated tools relying on both |

```bash
# --- Level 1: game only ---
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
"$LSREGISTER" -u "/Applications/UaRO.app" "/Applications/UaRO Settings.app" 2>/dev/null
rm -rf "/Applications/UaRO.app" "/Applications/UaRO Settings.app" "$GAME_DIR"
# Verify: neither app should resolve, and the game dir should be gone
"$LSREGISTER" -dump 2>/dev/null | grep -c "com.uaro" ;# expect 0
test -d "$GAME_DIR" && echo "still there" || echo "removed"

# --- Level 2: also drop the bottle ---
"$(command -v whisky)" delete "$BOTTLE_NAME"   # or remove via Whisky.app GUI
whisky list | grep -q "$BOTTLE_NAME" && echo "still there" || echo "removed"

# --- Level 3: also remove Whisky.app + the WhiskyWine runtime ---
rm -rf /Applications/Whisky.app ~/Applications/Whisky.app
rm -rf ~/Library/Application\ Support/com.isaacmarovitz.Whisky
brew uninstall --cask whisky 2>/dev/null   # no-op if it was sideloaded, not brewed
command -v whisky || echo "whisky CLI gone"

# --- Level 4: also remove shared infra (confirm nothing else needs these first) ---
softwareupdate --remove-rosetta 2>/dev/null   # only if truly nothing else needs Rosetta
# Homebrew's own uninstall is interactive/destructive to *everything* it manages —
# don't script this blind; point the user at https://github.com/Homebrew/install#uninstall-homebrew
# and let them run it themselves if they're certain.
```

**If Level 3+ is chosen, tell the user explicitly before they proceed:** Whisky's own distribution channels are permanently dead upstream — the Homebrew cask is disabled and the WhiskyWine/GPTK download endpoint 404s (see the "Why this exists" background). Re-installing later will **not** work by just re-running Step 3/4 against the live internet; it depends on the archived copy already saved to this repo's GitHub Release (`whisky-backup-2026-07-25` on `jirukouya/auRO-whisky-macOS-setup`, or wherever the user's own copy of that release lives). Confirm that backup still exists and is reachable before letting the user tear down their only working copy.

## Credits & Disclaimer

**Acknowledgments**
- The original step-by-step reference this skill was built from and hardened against real-world failures came from **@45rn0d3u5** on the uaRO Discord ([source document](https://docs.google.com/document/d/1ISi_iijWQuf5AeAh-ITtLYWm-My444x--d7rvQLiaL8/edit?tab=t.0)). This skill wouldn't exist without that groundwork — thank you.
- Thanks to **Isaac Marovitz**, creator of [Whisky](https://getwhisky.app/), the Wine wrapper this entire install path is built on. Whisky itself is no longer actively maintained (discontinued April 2025), but it's still the right tool for this job, and a fair amount of this skill exists specifically to keep it usable despite that.

**Disclaimer**
- This project is unofficial and not affiliated with, endorsed by, or supported by uaRO, Gravity Co., Whisky/Isaac Marovitz, or Apple.
- Provided as-is, with no warranty of any kind — use at your own risk. See *Known open issues* and *Common Gotchas* above for what's already known to be imperfect.
- This skill only reads/writes files under the directories it creates or is told to use (`$GAME_DIR`, the Whisky bottle, `/Applications/UaRO*.app`) plus standard Homebrew/system locations needed to install its own dependencies. It does not collect, transmit, or store any personal data, credentials, or telemetry — every credential prompt along the way (macOS admin password, uaRO account login) is handled directly by the user, never by this skill or the AI running it.
- Licensed under the [MIT License](./LICENSE) — see that file for the full text.
