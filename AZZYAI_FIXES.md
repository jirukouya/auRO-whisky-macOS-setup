# Installing and fixing AzzyAI on uaRO

AzzyAI is a third-party Lua AI for controlling a mercenary or homunculus. This file covers both halves: getting it onto a fresh uaRO install (below), and the five-cause fix for the "installs fine but never attacks" symptom every private-server install of it eventually hits (further down).

## Installing AzzyAI

**Source: [github.com/SpenceKonde/AzzyAI](https://github.com/SpenceKonde/AzzyAI)** — the author's own repo, still the canonical source even though the README says it's no longer actively maintained (last pushed 2020, no packaged Releases, so the download is the repo's own zip archive, not a versioned release asset). Never point a player at a random forum re-upload — this repo is public, verifiable, and confirmed reachable.

```bash
curl -fL --progress-bar -o ~/Downloads/AzzyAI-master.zip \
  https://github.com/SpenceKonde/AzzyAI/archive/refs/heads/master.zip
```

If the player would rather click through a browser instead of a terminal command: the repo's green **Code → Download ZIP** button produces the exact same file.

**Locate the game's `USER_AI` folder** — don't assume the path, a fresh uaRO install (via the companion `SKILL.md` in this repo) already has one with a default AI already in it:

```bash
find ~ -maxdepth 6 -type d -iname "USER_AI" 2>/dev/null
```

**Extract to a scratch folder first, then copy — never extract directly on top of `USER_AI`.** This is the one step most likely to be done wrong: the GitHub zip's internal layout nests everything one level deeper than AzzyAI's own historical packaged releases (the ones its `Documentation.pdf` was written against) — extracting it produces `AzzyAI-master/USER_AI/<the actual .lua files, AzzyAIConfig.exe, Documentation.pdf>`, not the flat `AzzyAI-master/<files>` the PDF describes. **What has to land in the game's real `USER_AI/` folder is the *contents* of `AzzyAI-master/USER_AI/`, not the `AzzyAI-master` folder itself and not a nested `USER_AI` folder inside it:**

```bash
mkdir -p /tmp/azzyai-extract
ditto -xk ~/Downloads/AzzyAI-master.zip /tmp/azzyai-extract
```

**Before copying, ask whether the player wants to keep any existing AI.** A fresh `USER_AI/` already has uaRO's own default mercenary/homunculus AI in it (`AI.lua` for homunculus, `AI_M.lua` for mercenary, among other files) — copying AzzyAI's version over the top replaces it. Most players installing AzzyAI want exactly that, but confirm rather than assuming, per AzzyAI's own documented caveat:

```bash
USER_AI_DIR="<the real path find just printed>"
cp -R /tmp/azzyai-extract/AzzyAI-master/USER_AI/. "$USER_AI_DIR/"
```

**Turn it on — this step is easy to forget and silently skip.** Files being present in `USER_AI/` does *not* mean AzzyAI is active for a character; it has to be switched on from inside the game, per-character, every time it's freshly enabled:
1. Start the game, log in to the character that should use it.
2. In chat, type `/merai` (mercenary) or `/hoai` (homunculus), repeating if needed until it confirms the AI has been customized.
3. Summon the mercenary/homunculus (or relog, if a homunculus is already out) so it actually picks up the new AI.

**Verify the install actually took, don't just trust step 2 above:**

```bash
ls "$GAME_DIR"/AAIStartM.txt "$GAME_DIR"/AAIStartH.txt 2>/dev/null
```

At least one of these (M for mercenary, H for homunculus, matching whichever was activated) should exist in the game's root folder — not `USER_AI/` — right after step 2's activation. **If neither file appears, AzzyAI isn't actually running yet** — this is AzzyAI's own documented signal for a failed install, not just a diagnostic log to read later.

**What almost certainly happens next, on uaRO specifically:** the mercenary/homunculus will follow around but never attack, regardless of config. This is expected on private servers — see *Root causes* below, and apply all five fixes as a matter of course on uaRO rather than waiting for the player to report it, since this project has already confirmed uaRO hits every one of them.

**One caveat on file versions:** the GitHub source isn't guaranteed byte-identical to the specific `AzzyAI 1.551` packaged release the fixes below were originally diagnosed against (file sizes differ slightly) — but the five root causes are long-standing, core AzzyAI logic, not version-specific quirks, and every patch below is applied by searching for the actual code pattern (never a hardcoded line number), so it holds regardless of exactly which build was downloaded.

## Fixing AzzyAI: "installs fine, but never attacks"

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
| 3 | `AI/USER_AI/M_Config.lua` (`H_Config.lua`) | `AutoDetectPlant=1` is also AzzyAI's stock default: the first time it sees a monster standing still, it's treated as a possible passive "plant"-type monster and excluded from targeting until it moves on its own | Set `AutoDetectPlant = 0` while diagnosing #4/#5 below — with those still broken, this setting alone can make it look like *everything* is a plant. Once #4/#5 are fixed, this becomes a genuine preference (see "Ignoring stationary/plant monsters" near the end) rather than something that needs to be off. |
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

## Ignoring specific monsters by species (e.g. an MVP)

AzzyAI has a real feature for this — a per-species tactics entry:
```lua
MyTact[classID]={TACT_IGNORE,SKILL_ALWAYS,KITE_NEVER,CAST_REACT,PUSH_SELF,DEBUFF_NEVER,CLASS_BOTH,RESCUE_OWNER,-1,SNIPE_OK,KS_NEVER,1,CHASE_NORMAL} --whatever monster this is
```
added to `M_Tactics.lua`/`H_Tactics.lua`, where `classID` is the monster's species/database ID (not its per-spawn actor GID, which changes every time it respawns).

**This does not work on a mercenary without a homunculus running alongside it, and there is no way around that.** `GetTact()` needs to resolve an actor's species before it can look up its `MyTact[classID]` entry — and the *only* engine call in this whole codebase that can do that is `GetV(V_HOMUNTYPE, v)`. Confirmed live: calling it from a mercenary's own AI context (`IsHomun(MyID)==0`) throws a hard Lua error (`bad argument #1 to 'tostring' (value expected)`) — it returns literally nothing, not even `nil`, for anyone other than a homunculus. The full constant list this codebase references (`V_ATTACKRANGE`, `V_HOMUNTYPE`, `V_HP`, `V_MAXHP`, `V_MAXSP`, `V_MERTYPE`, `V_MOTION`, `V_OWNER`, `V_POSITION`, `V_POSITION_APPLY_SKILLATTACKRANGE`, `V_SKILLATTACKRANGE`, `V_SKILLATTACKRANGE_LEVEL`, `V_SP`, `V_TARGET`) has no substitute. A mercenary without a homunculus spotter falls back to `GetClass()`, which only ever returns one of three generic buckets (`0` normal / `10` summoned / `11` plant) — never an actual species ID — so a `MyTact[classID]` entry just sits there unused.

The supported way to get real species data to a mercenary is `LiveMobID`: set `LiveMobID = 1` in **both** `H_Config.lua` and `M_Config.lua`, and keep an actual homunculus summoned near the mercenary. The homunculus writes `AI/USER_AI/MobID.lua` every tick with GID→species mappings for everything it can see (`GetV(V_HOMUNTYPE,v)` works fine there — the restriction is specifically about who's asking, not who's being asked about); the mercenary reloads that file every tick to populate its own lookup. Without a homunculus-capable class (Alchemist/Genetic-line), this path isn't available — the "AzzyAI Improved Data Gathering" AI the documentation also mentions as an alternative isn't bundled in this repo's AzzyAI release and hasn't been verified here.

### Practical fallback for mercenary-only setups: ignoring stationary/plant monsters

If per-species targeting isn't available, `AutoDetectPlant=1` is a usable (if approximate) substitute for the common case of "don't bother with monsters that just stand there." It's *behavior*-based, not species-based:
```lua
if (AutoDetectPlant==1 and IsActive[v]~=1) then
    if (motion is STAND, DAMAGE, or DEAD) then IsActive[v]=0  -- stays ignored
    else IsActive[v]=1 end                                    -- flips permanently attackable
end
```
A monster is skipped for as long as it's never shown anything but standing/taking-damage/dying since it first came into view. The moment it moves under its own power even once (walks, notices you, approaches), it's marked active for the rest of that spawn's life and gets attacked normally from then on. This will also catch ordinary aggressive monsters that happen to spawn standing still, and won't catch a mobile monster you specifically want ignored (an MVP that walks around, for instance) — it's a coarse "ignore idle things" switch, not a targeted ignore-list. Confirmed live on uaRO: correctly leaves alone monsters that never move, once #4/#5 above are already fixed (otherwise this setting alone was masking the real bug — see the table above).

## Reapplying after an AzzyAI reinstall

Reinstalling AzzyAI (copying a fresh release into `USER_AI/`) overwrites `AI_main.lua`, `AzzyUtil.lua`, and `M_Config.lua`/`H_Config.lua` back to stock, which reverts fixes #2-#5. Reapply them from this file. #1 needs no action either way.
