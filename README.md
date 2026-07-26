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

1. **Open Terminal anywhere**, and start an AI coding session there — either [Claude Code](https://claude.com/claude-code) (`claude`) or [OpenAI Codex CLI](https://github.com/openai/codex) (`codex`).

2. **Paste this whole thing:**
   ```
   Fetch SKILL.md from https://github.com/jirukouya/auRO-whisky-macOS-setup and follow it step by step to install uaRO on this Mac. Stop after each step and show me the progress table before continuing.
   ```

3. **From there, just answer what it asks.** It'll tell you before anything you need to personally do — logging into the uaRO download page, clicking through the installer wizard, typing your Mac password if macOS asks for it — and it won't move to the next step without checking with you first.

## Updating an existing install

Already installed uaRO with this skill before? Paste this whole thing to your AI session:

```
Fetch SKILL.md from https://github.com/jirukouya/auRO-whisky-macOS-setup — I already have uaRO installed, run Step 2a to check my existing install against the latest fixes, and apply anything that's missing.
```

It'll detect what's out of date (old keybind fix, missing crash-dialog mitigation, etc.) and only touch what's actually missing — it won't reinstall anything that's already working. See [CHANGELOG.md](./CHANGELOG.md) for what's changed release to release.

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

**Public.** These Whisky fixes are useful beyond just uaRO, so this repo's [Releases](../../releases) archive Whisky.app and its Wine runtime in case the upstream sources ever disappear for good.

## Changelog

Latest: **v0.2.0** — fixed in-game menu shortcuts (`Cmd+A`/`Cmd+Z`) via Option=Alt instead of breaking `Cmd+V` paste, and mitigated the post-Gecko patcher's "Program Error" crash dialog. Full history in [CHANGELOG.md](./CHANGELOG.md).

## Disclaimer

This is unofficial. Run it at your own risk:

- **No guarantees.** This is a personal project, shared as-is — see *Known open issues* in `SKILL.md` for what's already known to be imperfect, including one unresolved crash.
- **This patches a third-party binary.** The uaRO installer gets a few bytes changed to work around a Rosetta translation bug. A backup is made automatically first, but it's still altering someone else's executable.
- **Real changes to your Mac.** This installs Homebrew, Rosetta, Whisky, and two apps in `/Applications` — all reversible (see *Uninstalling* above), but not a sandboxed trial run.
- **No data collection.** Nothing here collects, transmits, or stores your personal data, credentials, or usage. Every login along the way (your Mac's admin password, your uaRO account) is handled directly by you — never by this skill or the AI running it.

## Acknowledgments

- **@45rn0d3u5** on the uaRO Discord, who wrote and shared the original [`install-uaro-mac` reference](https://docs.google.com/document/d/1ISi_iijWQuf5AeAh-ITtLYWm-My444x--d7rvQLiaL8/edit?tab=t.0) this skill was built on top of.
- **[Isaac Marovitz](https://github.com/IsaacMarovitz)**, creator of [Whisky](https://getwhisky.app/), the Wine wrapper this entire install path depends on.

## License

[MIT](./LICENSE) — free to use, modify, and share; provided as-is, with no warranty.
