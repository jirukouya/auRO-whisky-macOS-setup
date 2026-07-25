# uaRO on Apple Silicon, via Whisky

**This repo is one file that installs the uaRO Windows game on your Mac by talking to an AI, not by reading instructions yourself.**

[`SKILL.md`](./SKILL.md) is a self-contained playbook written *for an AI coding agent* (Claude Code or OpenAI Codex) to read and execute, not for a human to follow by hand. Hand it the file, say "install uaRO," and it drives the whole thing end to end. Curious what that actually involves? Open `SKILL.md` — it's all in there.

## The problem this solves

uaRO ([Ragnarok Online](https://en.wikipedia.org/wiki/Ragnarok_Online) private server) is a Windows-only game protected by **Gepard Shield 3.0** anti-cheat. The obvious approach — run it in a **Windows 11** VM (VMware Fusion) — turned into a dead end:

- More virtual CPUs → Gepard threw an error almost immediately.
- Fewer virtual CPUs → avoided the error, but the game stuttered badly within seconds.
- Disabling Windows Defender, or whitelisting the game instead → no effect either way.
- Every Visual C++ Redistributable from 2005 through 2026, x86/x64/ARM → no effect.
- Every graphics tweak (resolution, texture quality, DirectX version, graphics device, windowed vs. fullscreen) → no effect.

None of it mattered, because the actual blocker was never performance — it was Gepard Shield not working well with the **Windows 11 on ARM** processor that a VM on Apple Silicon has to run.

## The fix, and what made it hard

**Whisky** (a lightweight macOS Wine wrapper) sidesteps the problem: it translates the game's x86 Windows calls directly on macOS, no ARM Windows kernel involved. But Whisky itself is discontinued and broken in non-obvious ways:

- Its Homebrew cask and Wine-runtime download endpoint are both dead upstream.
- A required internal config file has to match an exact schema, or Whisky silently rejects it.
- iCloud Drive sync can relocate freshly-written files out from under an in-progress install.
- The game's patcher hard-depends on a Wine component (Gecko) with a one-shot install prompt.
- The Windows installer crashes under Rosetta unless two specific bytes in it are patched.

`SKILL.md` is every one of those fixes, plus the verification to catch it if any fails silently again — found by actually running the whole process once, end to end, on a real machine.

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

Same idea, in reverse: hand the AI this same `SKILL.md` and ask it to uninstall uaRO. Pick how much to undo:

| Level | Removes |
|---|---|
| 1 | Just the game |
| 2 | + the Wine bottle |
| 3 | + Whisky itself |
| 4 | + shared infra (Homebrew, Rosetta) |

## Status

Public. The fixes documented here (Whisky's dead infrastructure, the Gecko pitfall, the iCloud file-relocation bug, etc.) are broadly useful beyond this one game, and this repo's [Releases](../../releases) hold archived copies of Whisky.app and its Wine runtime in case the upstream sources ever disappear for good.

## Acknowledgments

- **@45rn0d3u5** on the uaRO Discord, who wrote and shared the original [`install-uaro-mac` reference](https://docs.google.com/document/d/1ISi_iijWQuf5AeAh-ITtLYWm-My444x--d7rvQLiaL8/edit?tab=t.0) this skill was built on top of.
- **[Isaac Marovitz](https://github.com/IsaacMarovitz)**, creator of [Whisky](https://getwhisky.app/), the Wine wrapper this entire install path depends on.

See `SKILL.md`'s closing *Credits & Disclaimer* section for the full write-up, including scope and no-warranty notes.

## License

[MIT](./LICENSE).
