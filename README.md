# uaRO on Apple Silicon, via Whisky

A Claude Code / Codex **skill** ([`SKILL.md`](./SKILL.md)) that installs and configures **uaRO** (a Ragnarok Online private server) on macOS — Homebrew, Rosetta 2, Whisky.app, the WhiskyWine runtime, a properly configured bottle, the uaRO installer, Rosetta-compatibility byte-patches, Wine Gecko, game configs, and two native-feeling launcher apps — fully end to end, on a Mac that's never seen any of this before.

## Why this exists

Before landing on Whisky, a lot of time went into fighting uaRO under **VMware Fusion**, with **Gepard 3.0** anti-cheat as the actual blocker the whole time. None of the "normal" VM tuning helped:

- More vCPUs → Gepard threw an error almost immediately.
- Fewer vCPUs → avoided the error, but the game stuttered badly within seconds.
- Disabling Windows Defender, or whitelisting `uaRO.exe` instead — no effect either way.
- Every Visual C++ Redistributable from 2005 through 2026, x86/x64/ARM — no effect.
- Every graphics tweak (resolution, texture quality, DirectX version, graphics device, windowed vs. fullscreen) — no effect.

Whisky (a lightweight Wine wrapper) turned out to be the actual fix — running the game closer to native, with no VM overhead, sidesteps Gepard's VM detection entirely. Once its two broken bits of infrastructure (Whisky's own Homebrew cask window and its dead GPTK download endpoint) were routed around and a handful of very real, non-obvious bugs were found by actually running the process once (a plist schema Whisky silently rejects, macOS's iCloud sync quietly relocating files mid-install, a Wine Gecko dependency the patcher can't run without), the result runs for hours with zero disconnects and a crisp, near-native-feeling UI.

## Credit

Built on top of an original community-shared `install-uaro-mac` reference script/writeup, then hardened by actually executing every step once end to end and fixing what broke.

## How to use this

On a fresh Mac, in a new Claude Code (or Codex) session:

1. Point it at `SKILL.md` in this repo.
2. Tell it to install uaRO.

That's it — `SKILL.md` is fully self-contained: every command, byte offset, config template, and gotcha needed is inlined, so no other file or prior context is required.

## Status

Private for now. The install procedure documented here (Whisky/Wine fixes, the Gecko pitfall, the iCloud file-relocation bug, etc.) is broadly useful beyond this one game, so this may get made public later — that's a separate decision from whether it works, and it works.
