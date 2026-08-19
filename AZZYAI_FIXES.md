# Fixing AzzyAI on uaRO

AzzyAI (a third-party Lua AI for controlling a mercenary or homunculus) installs fine on uaRO and reports "started successfully," but the mercenary/homunculus just stands there — no auto-attack, no matter how the config is tuned.

**This is not an install mistake.** AzzyAI was written against official Gravity server conventions. uaRO (an rAthena-class private server) allocates actor IDs differently, and AzzyAI's own documentation admits this class of problem outright: *"It is known and expected that AzzyAI will have targeting problems on most illegal private servers."* Five separate causes stack up to produce the "stands there doing nothing" symptom, and all five have to be fixed together — fixing only some of them still looks exactly like "not working."

This was diagnosed on a mercenary; the same code paths are shared with the homunculus AI (`AI.lua` uses the same `AI_main.lua`/`AzzyUtil.lua`), so the same fixes apply to `H_Config.lua` where `M_Config.lua` is named below.

## Symptom

AzzyAI installs, `/merai` (or `/hoai`) confirms the switch in chat, the mercenary/homunculus follows you around — and simply never attacks, regardless of `M_Config.lua`/`M_Tactics.lua` tuning.

## Root causes (all five needed)

| # | File | Cause | Fix |
|---|---|---|---|
| 1 | `AI/USER_AI/Const_.lua` | Version string is `"1.552"`; AzzyAI's own version-check regex truncates it to `"1.55"` and logs a false "wrong version" / "ranged pierce exploit" warning in `AAIStartM.txt`/`AAIStartH.txt` | **No fix needed** — cosmetic false positive, doesn't gate any AI logic. Safe to ignore. |
| 2 | `AI/USER_AI/M_Config.lua` (`H_Config.lua` for homunculus) | `StickyStandby=1` is AzzyAI's own stock default: the moment the mercenary enters its "follow" state (i.e. most of the time), it's silently forced into non-aggressive standby | Set `StickyStandby = 0` |
| 3 | `AI/USER_AI/M_Config.lua` (`H_Config.lua`) | `AutoDetectPlant=1` is also AzzyAI's stock default: the first time it sees a monster standing still, it's treated as a possible passive "plant"-type monster and excluded from targeting until it moves on its own | Set `AutoDetectPlant = 0` (unless you actually want plant-avoidance) |
| 4 | `AI/USER_AI/AI_main.lua`, ~line 3345 | `if (v > MagicNumber2) then Players[v]=1` classifies any actor ID above 100,000 as a player. **uaRO's monster GIDs are also above 100,000** (observed range: ~110,148,xxx), so every monster gets misclassified as a player and never enters the `Targets[]` table | `if (v > MagicNumber2 and IsMonster(v)==0) then` |
| 5 | `AI/USER_AI/AzzyUtil.lua`, `IsPlayer()` (~line 321) | Same 100,000-ID threshold, in a second, independent function. `GetTact()` calls `IsPlayer()` directly and returns "no tactic" (0 = don't attack) for anything it flags as a player — so even if #4 is fixed and a monster makes it into `Targets[]`, this is what actually kills the attack decision | `if (id>MagicNumber2 and IsMonster(id)==0) then` |

\#4 and #5 are the real bugs, and they're two **independent** functions that each hit the same wrong assumption (actor IDs above 100,000 = player) — this is why it's easy to fix one and still see the mercenary standing idle. Both have to be patched.

## Optional: engagement range for active farming

If the goal is aggressive auto-farming rather than defend-only guarding, keep these internally consistent in `M_Config.lua` — the "how far will it chase" bound should be `>=` the "how far will it look for a fight" distance, or you'll get monsters detected but never chased:

```lua
StationaryAggroDist  = 12
MobileAggroDist      = 12
StationaryMoveBounds = 14
MobileMoveBounds     = 14
```
(AzzyAI's own stock defaults are `12/7/14/9` — internally consistent already, just narrower while moving. The above just widens the mobile case to match.)

## Patches

**`AI_main.lua`:**
```lua
-- before:
if (v > MagicNumber2) then
    Players[v]=1
-- after:
if (v > MagicNumber2 and IsMonster(v)==0) then --uaRO monster IDs also exceed MagicNumber2
    Players[v]=1
```

**`AzzyUtil.lua`:**
```lua
-- before:
function IsPlayer(id)
	if (id>MagicNumber2) then
		return 1
	else
		return 0
	end
end
-- after:
function IsPlayer(id)
	if (id>MagicNumber2 and IsMonster(id)==0) then --same fix as AI_main.lua's classification loop
		return 1
	else
		return 0
	end
end
```

**`M_Config.lua`** (or `H_Config.lua`): set `StickyStandby = 0` and `AutoDetectPlant = 0`.

Neither `#4` nor `#5` touch `MagicNumber`/`MagicNumber2` themselves — a private server's monster and player ID ranges can overlap in ways a single static threshold can't cleanly separate, but `IsMonster()` (an engine-native call) is reliable regardless of ID magnitude, confirmed by direct log capture (see below). Cross-checking against it is safer than guessing a new threshold.

## How to verify (and how this was actually diagnosed)

AzzyAI ships a debug switch that isn't documented anywhere obvious. In `M_Extra.lua` (or `H_Extra.lua`), uncomment:
```lua
LogEnable["AAI_ACTORS"]=1
```
Every newly-seen actor gets logged to `AAI_ACTORS.log` in the game root, one line per actor: its raw GID, mertype, position, and the engine's own `IsMonster()` result. This is what proved the ID-range theory — real monsters showed `Is M=1` with GIDs around 110,148,xxx, while real players showed `Is M=0`, confirming `IsMonster()` itself is trustworthy and the bug is purely in AzzyAI's own ID-threshold shortcuts.

Steps:
1. Uncomment the line above, relog (or vap/resummon) so the edited Lua actually reloads — AzzyAI's scripts are `dofile`'d once at init, editing the file on disk doesn't affect an already-running instance.
2. Stand near monsters for a few seconds.
3. Read `AAI_ACTORS.log`. If your server's monster GIDs are also above `MagicNumber2` (100,000), you're hitting the same bug and the same fix applies.
4. Turn the log back off afterward (`--LogEnable["AAI_ACTORS"]=1`) — it writes a line for every newly-seen actor and there's no reason to keep it running once confirmed.

If you need to go one layer deeper (confirm whether the mercenary/homunculus is actually deciding to engage, not just seeing the target), add a temporary probe right after the `aggro`/`GetEnemyList()` call in `AI_main.lua`'s `OnIDLE_ST()` (search for `SelectEnemy(GetEnemyList(MyID,aggro))`) logging `aggro`, `HPPercent(MyID)`, `ShouldStandby`, `StickyStandby`, and the returned enemy-list count under a custom `LogEnable[...]` channel. This is what isolated cause #5 after #2-#4 were already fixed and the mercenary was still idle.

## Reapplying after an AzzyAI reinstall

Reinstalling AzzyAI (copying a fresh release into `USER_AI/`) overwrites `AI_main.lua`, `AzzyUtil.lua`, and `M_Config.lua`/`H_Config.lua` back to stock, which reverts fixes #2-#5. Reapply them from this file. #1 needs no action either way.
