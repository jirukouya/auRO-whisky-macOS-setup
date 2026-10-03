# uaRO on Apple Silicon, via Whisky

This repository provides an AI-executable setup skill for running the uaRO
Windows game on an Apple Silicon Mac through Whisky.

[`SKILL.md`](./SKILL.md) is the main execution playbook. It is written for
Claude Code, OpenAI Codex, GitHub Copilot, or another AI coding agent that can
read and operate on the local repository. The other files are supporting
references for troubleshooting, AzzyAI, and change history.

## Choose your route

Start with the prompt that matches the state of the Mac:

| Goal | Prompt to give the AI | Primary entry |
|---|---|---|
| Fresh install | `Read SKILL.md and install uaRO on this Mac via Whisky. Stop after each step and show the progress table before continuing.` | `SKILL.md` |
| Existing or partial install | `Read SKILL.md, inspect my existing uaRO Whisky installation, and apply only missing fixes. Do not reinstall working components.` | `SKILL.md` |
| Verify only | `Run a verify-only check of my existing uaRO Whisky installation. Do not install, rebuild, patch, or delete anything.` | `SKILL.md` |
| Repair a symptom | `Diagnose my existing uaRO Whisky installation first. Check the current state and identify the failing layer before changing anything.` | `SKILL.md` + `TROUBLESHOOTING.md` |
| Uninstall | `Read the uninstall section in SKILL.md, show me the exact removal scope and savedata backup plan, then wait before removing anything.` | `SKILL.md` |
| Install AzzyAI | `Read AZZYAI_FIXES.md and help me install AzzyAI after confirming the core uaRO setup is working.` | `AZZYAI_FIXES.md` |
| Repair AzzyAI | `Read AZZYAI_FIXES.md. AzzyAI is installed, but my mercenary or homunculus follows without attacking. Check first, then repair only the required files.` | `AZZYAI_FIXES.md` |

If you are starting from GitHub, open the repository in the AI coding agent
or ask it to read the current `SKILL.md` from this repository. The skill is
designed to stop before human-only actions such as account login, GUI clicks,
or administrator-password entry.

## What this skill solves

uaRO is a Windows-only Ragnarok Online private server protected by Gepard
Shield 3.0. On Apple Silicon, the practical route documented here is to run
the x86 Windows client directly through Whisky/Wine instead of putting it
inside a Windows-on-ARM virtual machine.

The difficult part is not just launching the game. Whisky is discontinued and
several components fail silently or depend on exact runtime details. The
playbook handles:

- Apple Silicon and macOS pre-flight checks.
- Homebrew, Rosetta 2, Whisky, and the archived WhiskyWine runtime.
- Bottle creation and configuration.
- The large, login-gated uaRO installer.
- Rosetta-compatible FCOM patches for `setup.exe`.
- Wine Gecko installation for the patcher.
- Game configuration, keyboard mapping, and launcher creation.
- Verification, repair, rollback, and optional `uaro-cli` tooling.
- Optional AzzyAI installation and repair after the core setup, with a
  deterministic USER_AI backup and replacement gate in `scripts/azzyai.py`.

The README stays at the decision and usage level. Exact commands, paths,
placeholders, and mandatory checks live in [`SKILL.md`](./SKILL.md).

## What the AI does vs. what you do

| The AI can handle | You must handle |
|---|---|
| Inspect the Mac, Whisky, bottle, runtime, files, and current state | Log in to your uaRO account |
| Install and configure public dependencies | Enter a Mac administrator password when macOS asks |
| Download public archives and build launchers | Click through the Windows installer wizard |
| Apply reversible configuration and binary patches | Confirm the game reaches the requested in-game state |
| Run file, runtime, and behavior checks | Decide the final uninstall scope or optional launcher trade-offs |

The AI should not ask you to paste passwords, and it should not report success
only because a command returned exit code 0.

## What counts as success

The current playbook uses three completion gates for the same bottle and game
directory:

| Gate | Evidence |
|---|---|
| Target | The intended files, configuration, backups, launcher bundles, and paths read back correctly |
| Execution | The actual launcher uses the resolved Whisky CLI, bottle, `WINEPREFIX`, DLL overrides, and runtime intended for this install |
| Behavior | Settings round-trip, the patcher advances beyond `Getting patch_main.txt...`, and the game reaches a stable login or equivalent user-visible result |

A generated launcher, a manifest, a running process, or a successful command
alone is not proof that the game is working.

## Requirements

- An Apple Silicon Mac (M1 or later).
- macOS 14 (Sonoma) or newer.
- Approximately 15–20 GB of free disk space.
- Xcode Command Line Tools; Homebrew may offer to install them during Step 1.
- A uaRO account, because the installer download is behind uaRO's login page.
- Time to perform the human-only installer and first-run checks.

## Recovery boundary

Git restores the repository, its contracts, tests, fixtures, and installation
playbook. It does not restore machine state or private account data.

| State | Recoverable from Git | Recovery still needed |
|---|---|---|
| Code, contracts, tests, fixtures, and docs | Yes | Clone or restore the canonical repository |
| Homebrew, Rosetta, Whisky, WhiskyWine, Wine Gecko | No | Reinstall or verify the machine dependencies |
| uaRO installer and account session | No | Log in and download the installer again |
| Bottle, game files, savedata, and AzzyAI user configuration | No | Restore from the user's own backups or reinstall |
| TCC, Keychain, administrator access, and signing environment | No | Re-authorize the new machine when macOS prompts |

The repository records the required categories and verification routes; it
does not store passwords, tokens, private keys, or account credentials.

The procedure documents a real end-to-end run on Apple Silicon macOS 26.5.2.
That is evidence for the documented route, not a guarantee for every future
macOS release, uaRO installer build, or Gepard Shield update.

## How to use it

### Desktop AI app

Open the repository in a coding-capable AI app, then use one of the route
prompts above. The AI will show a progress table and stop at each approval
checkpoint. You may still need to bring an installer window or Wine dialog to
the front manually.

### Terminal AI tool

Open a terminal in the repository root and ask the agent to read and follow
`SKILL.md`. A fresh session can use:

```text
Read SKILL.md from this repository and install uaRO on this Mac via Whisky.
Use the progress table, stop after each step, and wait for my confirmation.
```

Do not ask the agent to run the entire process as one unreviewed command
chain. The setup changes system state and includes GUI and account steps that
need a human checkpoint.

## Existing installs and AzzyAI

For an existing uaRO install, start with the verify or repair route instead of
reinstalling. The skill checks the actual bottle, game directory, launcher
bundles, configuration, and known fixes before deciding what to touch.

AzzyAI is optional and is not part of the core completion gate. Read
[`AZZYAI_FIXES.md`](./AZZYAI_FIXES.md) only after the core uaRO setup is working.
It covers both a fresh AzzyAI installation and repair of an existing setup
where the mercenary or homunculus follows but does not attack.

## Troubleshooting

Use [`TROUBLESHOOTING.md`](./TROUBLESHOOTING.md) when a mandatory verification
fails or a known symptom appears. The reference is indexed by category so the
AI can jump to the relevant issue instead of rereading the entire install
flow.

Typical routing:

| Symptom | First check |
|---|---|
| Patcher stays on `Getting patch_main.txt...` | Gecko installation and patcher behavior verification |
| `setup.exe` illegal-instruction failure | FCOM target context, backup, and byte-diff verification |
| Existing install lacks a newer keyboard or launcher fix | `2a. Detect existing state` and the adopt/repair route |
| Game disconnects or crashes after a known stage | Capture the exact symptom and runtime evidence before changing settings |
| Launcher opens but the game is not proven usable | Run the execution and behavior gates; do not infer success from the launcher |

## Verification status

The repository distinguishes between what has been tested on a real target
and what remains environment-dependent:

- The documented route has been exercised on a real Apple Silicon Mac, including
  runtime setup, bottle configuration, Gecko, FCOM handling, launchers, and
  first-run checks.
- Exact behavior can still vary by macOS version, display, uaRO installer build,
  server-side patches, and the state of an existing bottle.
- The optional direct Game launcher skips the patcher update check and therefore
  must not be treated as a permanent replacement for the Patcher launcher.
- A future installer build may move or add binary patch sites. The skill must
  verify context and stop when the expected bytes do not match.

When evidence is incomplete, the correct result is an unconfirmed or blocked
status, not a confident-sounding success message.

## Uninstalling

Ask the AI to show the exact scope before removing anything. The current skill
backs up `savedata` first and uses recoverable `trash` removal for filesystem
targets where available. Homebrew and Rosetta removal remain separate
package-manager/system operations and require an additional dependency check.

| Level | Removes |
|---|---|
| 1 | Launcher apps, game files, staged installer files, and optional `uaro-cli` |
| 2 | Level 1 plus the Whisky bottle |
| 3 | Level 2 plus Whisky and its WhiskyWine runtime |
| 4 | Level 3 plus shared Homebrew and Rosetta infrastructure |

## Status and changelog

**Public.** The repository is maintained as a practical, evidence-driven
Whisky route for uaRO on Apple Silicon.

The current version is recorded once in the frontmatter of
[`SKILL.md`](./SKILL.md). See [`CHANGELOG.md`](./CHANGELOG.md) for the history
of fixes and documentation changes.

## Disclaimer

This is unofficial software documentation. Use it at your own risk:

- It is not affiliated with or endorsed by uaRO, Gravity, Whisky, or Apple.
- It patches a third-party executable to work around a Rosetta translation
  issue. The playbook creates backups before patching.
- It installs Homebrew, Rosetta, Whisky, launcher apps, and optionally
  `uaro-cli`; these are real system changes, not a sandboxed trial.
- It does not collect or transmit credentials, personal data, or telemetry.
  Account logins and administrator-password prompts are handled directly by you.

## Acknowledgments

- **@45rn0d3u5** on the uaRO Discord for the original install reference.
- **Rhya** for practical help and troubleshooting support during the uaRO setup.
- **[Isaac Marovitz](https://github.com/IsaacMarovitz)** for creating Whisky.

## License

[MIT](./LICENSE) — free to use, modify, and share; provided as-is, with no warranty.
