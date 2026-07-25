# uaRO on Apple Silicon, via Whisky

**This repo is one file that installs a Windows game on your Mac by talking to an AI, not by reading instructions yourself.**

[`SKILL.md`](./SKILL.md) is a complete, self-contained playbook written *for an AI coding agent* (Claude Code or OpenAI Codex) to read and execute — not for a human to follow by hand. Hand it the file, say "install uaRO," and it drives the whole thing: Homebrew, Rosetta 2, Whisky.app, the WhiskyWine runtime, a properly configured Wine "bottle," the uaRO installer itself, a couple of binary compatibility patches, a required Wine Gecko component, game config files, and two double-clickable launcher apps in `/Applications` — checking in with you at every step, in plain language, telling you exactly what (if anything) you need to click or type.

## The problem this solves

uaRO ([Ragnarok Online](https://en.wikipedia.org/wiki/Ragnarok_Online) private server) is a Windows-only game protected by **Gepard Shield 3.0** anti-cheat. The obvious approach — run it in a Windows VM (VMware Fusion) — turned into a dead end:

- More virtual CPUs → Gepard threw an error almost immediately.
- Fewer virtual CPUs → avoided the error, but the game stuttered badly within seconds.
- Disabling Windows Defender, or whitelisting the game instead → no effect either way.
- Every Visual C++ Redistributable from 2005 through 2026, x86/x64/ARM → no effect.
- Every graphics tweak (resolution, texture quality, DirectX version, graphics device, windowed vs. fullscreen) → no effect.

None of it mattered, because the actual blocker was never performance — it was Gepard detecting it was running inside a VM at all.

## The fix, and what made it hard

**Whisky** (a lightweight macOS Wine wrapper) sidesteps the problem entirely: it runs the Windows game close to native, with no VM layer for Gepard to detect. That part was quick to figure out. Getting there reliably was not, because Whisky itself has real problems:

- Whisky was **discontinued by its creator in April 2025** — its Homebrew installer cask is disabled upstream, and the CDN it downloads its Wine runtime from returns a hard 404.
- Whisky's own "Install GPTK" button in-app shows a fake instant success and silently leaves an empty folder behind.
- The file that tells Whisky "the Wine runtime is installed" has to match an exact internal schema — a plausible-looking but wrong version of that file fails silently.
- macOS's iCloud Drive sync can relocate freshly-downloaded/extracted files out from under an in-progress install, tens of seconds after they were written — breaking things with a cryptic Wine file-not-found error.
- The game's patcher hard-depends on a Wine component (Gecko) that has a one-shot install prompt — decline it once by mistake, and there's no easy way back.
- The Windows installer itself crashes under Rosetta translation unless two specific bytes in it are patched first.

None of these are documented anywhere as a checklist — they were each found the hard way, by actually running the whole process end to end once, on a real machine, and fixing what broke. `SKILL.md` is the result: every one of those fixes, plus the verification step that catches it if it silently fails again, written up as instructions an AI agent can follow with no other context. The payoff: uaRO running for hours with zero disconnects and a crisp, near-native UI.

## How to actually run this

1. **Get `SKILL.md` onto the Mac you want to install uaRO on.** Either clone the whole repo:
   ```bash
   git clone https://github.com/jirukouya/auRO-whisky-macOS-setup.git
   cd auRO-whisky-macOS-setup
   ```
   or just download `SKILL.md` by itself and put it anywhere convenient.

2. **Open Terminal in that folder**, and start an AI coding session there — either [Claude Code](https://claude.com/claude-code) (`claude`) or [OpenAI Codex CLI](https://github.com/openai/codex) (`codex`).

3. **Tell it to run the skill.** Something like this is enough:
   > Read SKILL.md in this folder and follow it step by step to install uaRO on this Mac. Stop after each step and show me the progress table before continuing.

4. **From there, just answer what it asks.** It'll tell you before anything you need to personally do — logging into the uaRO download page, clicking through the installer wizard, typing your Mac password if macOS asks for it — and it won't move to the next step without checking with you first.

## What you'll need

- A Mac with **Apple Silicon** (M1 or later) on **macOS 14 (Sonoma) or newer** — Whisky itself requires both; there's no path through this skill on an Intel Mac.
- Roughly **15-20GB of free disk space**.
- A **uaRO account** — the installer download sits behind a login wall on uaRO's own site, so getting the installer file itself is always a manual, logged-in step no AI can do on your behalf.

## Uninstalling

Same idea, in reverse: hand the AI this same `SKILL.md` and ask it to uninstall uaRO. The file has a tiered rollback built in (game only → +Wine bottle → +Whisky itself → +shared infra like Homebrew/Rosetta), so you can undo as much or as little as you want.

## Status

Public. The fixes documented here (Whisky's dead infrastructure, the Gecko pitfall, the iCloud file-relocation bug, etc.) are broadly useful beyond this one game, and this repo's [Releases](../../releases) hold archived copies of Whisky.app and its Wine runtime in case the upstream sources ever disappear for good.

## Acknowledgments

- **@45rn0d3u5** on the uaRO Discord, who wrote and shared the original `install-uaro-mac` reference this skill was built on top of.
- **[Isaac Marovitz](https://github.com/IsaacMarovitz)**, creator of [Whisky](https://getwhisky.app/), the Wine wrapper this entire install path depends on.

See `SKILL.md`'s closing *Credits & Disclaimer* section for the full write-up, including scope and no-warranty notes.

## License

[MIT](./LICENSE).
