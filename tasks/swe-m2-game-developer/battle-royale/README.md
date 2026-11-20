# Battle royale

The task develops a multiplayer battle royale game across four steps. It starts
with the [first-step instruction](steps/01-build-game/instruction.md) and the
component briefs and reference assets under [workdir](steps/01-build-game/workdir/).
The checked-in implementation and package tools cover Step 01. The briefs
and reference experiment links below document Steps 02–04.

## Play Basin Signal

The route-and-search build has a ready Oddish **Game** capture. Choose **Play
in browser**, select **L4**, and click **Click to Start** when the stream opens.
Press **P** for solo practice and wait for all four slots to fill. Press
**Enter**, pick **F3** for Relay Station or **F4** for Survey Camp, and press
**Enter** to deploy. Press **E** at the landing to collect the rifle. The
live L4 test verified the sequence at Relay Station and confirmed both
opening forecasts across a match and rematch. The Linux downloads below
are available for local play.
[Route-and-search Game tab](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a?trial=swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a-0&tab=game)
· [Browser-tested practice build](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460?trial=swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460-11&tab=game)

The reference builds below include the game at each milestone. For Stages 1–3,
extract the Linux archive and run `./BattleRoyale.sh -windowed` in two processes.
Press **F1** in the host and **F2** in the guest. Press **Enter** in both
windows to ready up. In Stage 3, choose Relay Station with **F3** or Survey Camp
with **F4**, then press **Enter** to confirm in each window. The launcher requires
a Vulkan-capable Linux system.
The Stage 2 and 3 archives also rendered the Entry lobby offscreen on this WSL
host with `-vulkan -AllowCPUDevices`. Both downloads passed the two-client
keyboard playtest. Both Oddish Game captures now show the two-player lobby.
Use the Linux builds for a verified two-player match.
[Stage 2 Game preview](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage02-dashboard-1b9a3b06?trial=swe-m2_game-development_battle-royale-stage02-dashboard-1b9a3b06-11&tab=game)
· [Stage 3 Game preview](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage03-dashboard-dd35cb31?trial=swe-m2_game-development_battle-royale-stage03-dashboard-dd35cb31-0&tab=game)

| Milestone | Reference experiment | Playable build | Verifier report |
| --- | --- | --- | --- |
| 01 — Core match | [Two-client reference](https://www.oddish.app/experiments/de2a0309) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-local-verification-23b6ef35?trial=swe-m2_game-development_battle-royale-local-verification-23b6ef35-19&tab=files&file=steps%2F01-verify-basin%2Fverifier%2FBasin-Signal-linux.tar.gz) | [Round report](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-local-verification-23b6ef35?trial=swe-m2_game-development_battle-royale-local-verification-23b6ef35-19&tab=files&file=steps%2F01-verify-basin%2Fverifier%2Fround-smoke.json) |
| 02 — Map and match flow | [Map and zone reference](https://www.oddish.app/experiments/2c066e48) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage02-linux-download-cec51a27?trial=swe-m2_game-development_battle-royale-stage02-linux-download-cec51a27-0&tab=files&file=steps%2F02-map-and-match-flow%2Fverifier%2FBasin-Signal-Stage-02-Linux.tar.gz) · [Browser preview run](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage02-dashboard-1b9a3b06?trial=swe-m2_game-development_battle-royale-stage02-dashboard-1b9a3b06-11) | [Zone and rematch](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-zone-variation-calibration-bc7a916d?trial=swe-m2_game-development_battle-royale-zone-variation-calibration-bc7a916d-6&tab=files&file=steps%2F02-map-and-match-flow%2Fverifier%2Fstep02-zone-smoke.json) |
| 03 — Deployment and equipment | [Equipment reference](https://www.oddish.app/experiments/3c97e78a) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage03-linux-download-ccb59a0b?trial=swe-m2_game-development_battle-royale-stage03-linux-download-ccb59a0b-0&tab=files&file=steps%2F03-deployment-and-equipment%2Fverifier%2FBasin-Signal-Stage-03-Linux.tar.gz) · [Browser preview run](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-stage03-dashboard-dd35cb31?trial=swe-m2_game-development_battle-royale-stage03-dashboard-dd35cb31-0) | [Deployment and equipment](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-equipment-calibration-065306e1?trial=swe-m2_game-development_battle-royale-equipment-calibration-065306e1-0&tab=files&file=steps%2F03-deployment-and-equipment%2Fverifier%2Fstep03-calibration.json) |
| 04 — Dedicated multiplayer | [Four-stage reference](https://www.oddish.app/experiments/a80fadc7) | [Download Linux client](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-packaged-clients-calibration-edb792ef?trial=swe-m2_game-development_battle-royale-packaged-clients-calibration-edb792ef-1&tab=files&file=steps%2F04-dedicated-multiplayer%2Fverifier%2FBasin-Signal-Linux.tar.gz) | [Dedicated Editor multiplayer](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-four-player-editor-calibration-22192d84?trial=swe-m2_game-development_battle-royale-four-player-editor-calibration-22192d84-13&tab=files&file=steps%2F04-dedicated-multiplayer%2Fverifier%2Fstep04-multiplayer-smoke.json) |
| Solo practice | [Practice Oracle](https://www.oddish.app/experiments/933a9674) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-match-c4884632?trial=swe-m2_game-development_battle-royale-practice-match-c4884632-4&tab=files&file=steps%2F01-practice-match%2Fverifier%2FBasin-Signal-Stage-Practice-Linux.tar.gz) | [Practice and rematch](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-match-c4884632?trial=swe-m2_game-development_battle-royale-practice-match-c4884632-4&tab=files&file=steps%2F01-practice-match%2Fverifier%2Fpractice-smoke.json) |
| Covered landings | [Opening Oracle](https://www.oddish.app/experiments/ef33c499) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-opening-33b1d378?trial=swe-m2_game-development_battle-royale-practice-opening-33b1d378-0&tab=files&file=steps%2F01-practice-match%2Fverifier%2FBasin-Signal-Stage-Practice-Opening-Linux.tar.gz) | [Pickup and exit at both sites](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-opening-33b1d378?trial=swe-m2_game-development_battle-royale-practice-opening-33b1d378-0&tab=files&file=steps%2F01-practice-match%2Fverifier%2Fpractice-smoke.json) |
| Route rotation | [Route Oracle](https://www.oddish.app/experiments/e1069683) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-route-rotation-f9c14122?trial=swe-m2_game-development_battle-royale-practice-route-rotation-f9c14122-3&tab=files&file=steps%2F01-practice-match%2Fverifier%2FBasin-Signal-Stage-Practice-Route-Rotation-Linux.tar.gz) | [Road and trail replays](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-route-rotation-f9c14122?trial=swe-m2_game-development_battle-royale-practice-route-rotation-f9c14122-3&tab=files&file=steps%2F01-practice-match%2Fverifier%2Froute-smoke.json) |
| Route rotation and opponent search | [Combined Oracle](https://www.oddish.app/experiments/a28cfcee) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a?trial=swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a-0&tab=files&file=steps%2F01-practice-match%2Fverifier%2FBasin-Signal-Stage-Practice-Opponent-Search-Linux.tar.gz) | [Route replays](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a?trial=swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a-0&tab=files&file=steps%2F01-practice-match%2Fverifier%2Froute-smoke.json) · [Contact replay](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a?trial=swe-m2_game-development_battle-royale-practice-opponent-search-5ff6329a-0&tab=files&file=steps%2F01-practice-match%2Fverifier%2Fcontact-smoke.json) |
| Route-and-search Game menu | [Game preview Oracle](https://www.oddish.app/experiments/d20a9ba3) | [Download Linux](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a?trial=swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a-0&tab=files&file=verifier%2FBasin-Signal-Stage-Opponent-Search-Dashboard-Linux.tar.gz) | [Packaged menu](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a?trial=swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a-0&tab=files&file=verifier%2Fdashboard-practice-smoke.json) · [Editor menu](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a?trial=swe-m2_game-development_battle-royale-opponent-search-dashboard-1328689a-0&tab=files&file=verifier%2Fdashboard-editor-smoke.json) |

### Play from WSL

All four Linux reference builds are already extracted in this workspace. Run
the following command from any WSL terminal to open both Stage 4 windows.

```bash
bash ~/workspace/abundant/swe-marathon-2/tasks/swe-m2-game-developer/battle-royale/scripts/play_wsl.sh
```

The guest waits for the host and connects automatically. Use **Alt+Tab** if
the game windows are behind the terminal. Press **Enter** in each window to
ready up, then choose **F3** or **F4** and press **Enter** to confirm. Closing
either game window ends this playtest.

Add `--stage 1`, `--stage 2`, or `--stage 3` to the command to open an earlier
build. In those builds, press **F1** in the left window and wait for the host
lobby before pressing **F2** in the right window. Use `host` and `guest` after
the stage option to launch the windows from separate terminals. An extracted
Linux directory can be supplied after `play`, `host`, or `guest`.

Add `--stage sonnet` to play the earlier Stage 1 Sonnet submission from its
extracted Linux archive. The second window joins the port opened by the host.
Click **Ready** in both windows once the lobby shows two players.
[Sonnet experiment](https://www.oddish.app/experiments/d6669854) · [Sonnet Linux archive](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-sonnet-replay-03da50ae?trial=swe-m2_game-development_battle-royale-sonnet-replay-03da50ae-4&tab=files&file=steps%2F01-build-game%2Fverifier%2FBattle-Royale-Duel-linux.tar.gz)

The solo practice build is extracted in this workspace. Add `--stage practice`
to open one window with three scripted opponents. Wait for the lobby to fill,
press **Enter**, choose a landing area with **F3** or **F4**, and press **Enter**
to confirm. The WSL command selects the checksum-verified archive with the
relaunch fix. The dashboard prototype completed a match in both the packaged
game and the Editor runtime. Both verifiers confirmed that all three
opponents exited when the host stopped. Its Oddish Game tab has published
the menu capture. An L4 browser playtest streamed the menu, accepted **P**,
filled the four-player lobby, and ran a round and a rematch from keyboard input.
On another Linux machine, extract the archive and run `./play-practice.sh` from
its `Linux` directory. The archive uses UDP port 7781 by default.
[Dashboard practice Game tab](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460?trial=swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460-11&tab=game)
· [Linux build with the in-game practice menu](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460?trial=swe-m2_game-development_battle-royale-practice-match-dashboard-d32f9460-11&tab=files&file=verifier%2FBasin-Signal-Stage-Dashboard-Practice-Linux.tar.gz)

Add `--stage dashboard` to open the extracted route-and-search Game
menu from WSL. Press **P** in its game window to start solo practice.
Use `--stage opening-pilot` to open the verified feedback-pilot Oracle
with the sheltered pickup at each landing. Press **P** to play against
three opponents.
In the dashboard practice Game tab above, choose **Play in browser**
and select **L4**. Click **Click to Start** in the player and press **P**.
When all four slots are connected, press **Enter**. Choose Relay Station with
**F3** or Survey Camp with **F4** and press **Enter** to confirm. The newer
route-and-search build has passed its native match checks and has a published
Game capture.

Add `--stage covered` to play the covered landings. Ready up with **Enter**,
choose Relay Station with **F3** or Survey Camp with **F4**, and press
**Enter** to confirm. Use **E** to take the rifle and **A** or **D** to go
around the screening wall.

Add `--stage opponents` to open the build with both route rotation and
opponent search. The upcoming boundary and its direction appear on the
tactical map and countdown. Use the same deployment and pickup keys.
Use `--stage route` for the separate route rotation milestone.

The WSL launcher uses Unreal's `-AllowCPUDevices` flag. Two 640×360 windows
rendered through Mesa llvmpipe, agreed on the match winner, and started a rematch.
Expect lower frame rates with this software renderer. The extracted copy includes
local PulseAudio client libraries. Both launch commands opened WSLg's RDP audio
output and joined the same lobby.
[Unreal launch flags](https://dev.epicgames.com/documentation/en-us/unreal-engine/unreal-engine-command-line-arguments-reference?lang=en-US)
· [WSLg audio](https://github.com/microsoft/wslg#drawing-to-the-screen)

### Stage 4 listen playtest on Linux

For a two-player Stage 4 match, start the host from the extracted Linux directory.

```bash
./BattleRoyale.sh '/Engine/Maps/Entry?listen' -windowed -port=7777
```

Start the guest in a second window. This connects directly to the host on the
same machine.

```bash
./BattleRoyale.sh 127.0.0.1:7777 -windowed
```

Press **Enter** in both windows to ready up. Choose Relay Station with **F3**
or Survey Camp with **F4**, then press **Enter** to confirm. The listen match
has two player slots. The four-stage reference experiment covers the separately
hosted dedicated Editor scenarios.

## Basin Signal roadmap

The first release is a playable Unreal Engine 5 game for two human opponents on
one original survey-basin map. Players deploy, loot, move with the safe zone,
fight to be the last survivor, and start a fresh round. Use PUBG
as a reference for how loot, terrain, vehicles, and the safe zone create route
choices under time pressure. Give Basin Signal its own geography, props, HUD,
and audio. [PUBG design notes on the safe zone](https://pubg.com/en/news/10280)

Basin Signal already has a Linux build with the core systems. The live run
verified packaging, map startup, a shared draw, and a fresh round from both
clients. The Oddish baseline scores delivery, packaging, and map startup. Step
01 needs gameplay evidence across the current brief before it can score those
behaviors.
[Basin Signal live result](https://www.oddish.app/experiments/de2a0309)

### Implementation steps

Each step gives the candidate the next request in the same trial. After Step 01,
the candidate continues from their own editable Unreal project in
`/workspace/submission`. Each delivery includes `BattleRoyale.uproject` and the
project `README.md`, updated for the current build, controls, and session flow.

| Step | What the candidate builds | What carries forward |
| --- | --- | --- |
| [01 — Build the game](steps/01-build-game/instruction.md) | Deliver the complete two-opponent match from the ten component briefs, including movement, combat, loot, driving, zone pressure, and rematch. | Establish the Unreal project, playable loop, and documented Linux delivery. |
| [02 — Map and match flow](steps/02-map-and-match-flow/instruction.md) | Develop the relay station, survey camp, and quarry. Vary the closing area and show both safe-zone boundaries during warnings so players can react to route changes. | Keep the two-player session flow, combat, inventory, driving, and results from Step 01. |
| [03 — Deployment and equipment](steps/03-deployment-and-equipment/instruction.md) | Add starting-location tradeoffs, armor that wears down, interruptible healing, and limited space for supplies and reserve rounds. | Keep the map and zone cues from Step 02 and the two-player match rules. Extend inventory and reset behavior to cover the new equipment. |
| [04 — Dedicated multiplayer](steps/04-dedicated-multiplayer/instruction.md) | Build a dedicated Linux server for two to four human opponents. Exercise contested resources, disconnects, and rematches under both local and degraded network conditions. | Keep the map, deployment, equipment, driving, combat, zone, and last-survivor loop. The server takes over hosting and supports a configurable roster. |

Aerial insertion, attachments, supply drops, larger lobbies, reconnect,
spectating, and squads are candidates for later requests after playtesting the
four-step game.

### How the challenge grows

- Step 01 asks for the complete multiplayer match. Actions that look simple in
  one window, like picking up ammunition or entering a vehicle, must produce
  one shared result when both players act at the same time.
- Step 02 puts the map and zone schedule in tension. A road lets a player move
  quickly while exposing them. The longer covered route can be worth taking
  until the next safe area changes. Reaching different final landmarks should
  call for different routes from the same starting positions.
- Step 03 links actions across systems. Carrying heavier armor leaves less
  room for reserve ammunition and heals. Taking a hit during a heal should
  apply damage without granting health or spending the supply. A rematch must
  reset those decisions as well as the map and player health.
- Step 04 asks the agent to generalize prior decisions to a dedicated process
  and a larger roster. Delayed packets and departures can change the order in
  which actions arrive, while ownership, elimination, and the result still
  converge across the clients.

### Practice match difficulty experiment

Use the published practice match as the starting build. The next assignment
asks the agent to make route and equipment choices matter as the zone closes,
then revise the game after watching a playtest. Keep the single-window match
with three opponents so one person can play every revision.
[Practice baseline](https://www.oddish.app/experiments/933a9674)

The baseline already gives the player two paths from Relay Station to Survey
Camp. The road is 85.0 m and the covered trail is 138.5 m. At the configured
walk speed they take 18.5 s and 30.1 s in a straight-through traversal. The
first warning lasts 34 s, and both complete paths fit inside the first target
circle for all three final landmarks. These are estimates from the exact
published source, excluding deployment, obstacles, loot stops, and combat.
The opponents seek visible targets and move toward the safe-zone center as
the perimeter approaches. Their next decision drops an occluded target and
picks from the visible actors again. The code retains no last-seen position
to search.

A keyboard replay on the packaged build also found a problem before the zone
mattered. After landing at Relay Station and moving forward for three seconds,
the player was eliminated in the first run and had 52 health in the repeat.
The same input after landing at Survey Camp left the player at 100 health.
Both Relay runs started taking hits within three seconds. These are three
opening replays on the software renderer. They motivate a case for reaching
cover and nearby loot from each landing site.

| Stage | Assignment | Evidence to collect |
| --- | --- | --- |
| Route and equipment choices | Give each landing a reachable cover and loot option. Give the player time to read the next boundary and choose between a fast route and a route with cover and useful supplies. Make those advantages matter in different matches. | Replay the opening from each landing to reach cover and collect equipment. Then drive both routes from the same deployment and starting equipment in each scenario. Record travel time, health at entry into the new safe area, and useful supplies acquired. Include a tight rotation and one with more time and pressure on the exposed route. Check that the outcomes give a reason to choose differently. |
| Opponents under pressure | Make opponents act on what they can observe. Give the player a chance to break contact and use another route while opponents still respond to the closing area. | Break sight at cover, then vary whether the player reappears in view or stays hidden. Record pursuit, search, damage, and rotation. Replay from a different location and check that the response follows the same rules. |
| Revision from playtest | Hand the agent a replay of a specific gameplay problem and ask for an updated build. | Reproduce the problem on the starting build, replay it on the revision, then vary the timing and position. Check the full match and rematch on the revised build. Have a player compare the two builds without identifying the revision. |

Collect outcomes from normal controls and the running game. Use stable launch
and match completion as delivery checks. Report gameplay results and player
feedback alongside them. Use the practice release as a control for the
initial route cases and for a replay with loss of sight. Confirm that each
case observes the behavior it claims to measure before it contributes reward.

For the first feedback experiment, give both groups the same starting project,
revision request, tools, and compute budget. Give one group a failed playtest
with input timing, selected state, and a screenshot or clip. Compare the
resulting builds on held-out starts, circle layouts, and opponent positions.
Keep build and complete-match checks as gates. Report route choice, cover and
opponent behavior, and blind player preferences as separate outcomes. The
first comparison measures whether agents use playtest feedback to improve a
build. Training model weights would require a separate collection of
trajectories and an evaluation on unseen game briefs.

The opening pilot starts both groups from the earlier browser project. Both
get the same request for sheltered pickup and usable exits at Relay Station
and Survey Camp. The feedback group also receives the actual failed Relay
replay, with key timing and a frame of the unarmed player after elimination.
The current bundles have 88 identical files, including the prompt, starter,
Unreal environment, Oracle, and verification scripts. A readback of every
registered file in versions 2 and 3 matched the frozen bundle hashes. The
feedback version adds the replay note and frame. The version 2 Oracle
scored `1.0` at 15:44 UTC. Both replays started with 100 health and collected
24 loaded rounds at each landing. All four exits traveled about 9.5–9.6 m, with the
player alive at the end of each walkout. The replays used different opponent
slot assignments and each completed a match and rematch. The packaged and
Editor practice menus also passed. After checking the saved reports and
registered task files, the launch gate submitted one Sonnet 5.5 Max trial per
condition. Player preference data has yet to be collected.
[Opening pilot Oracle](https://www.oddish.app/experiments/fd808ed0)
· [Oracle Linux build](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opening-feedback-pilot-33a61f67?trial=swe-m2_game-development_battle-royale-opening-feedback-pilot-33a61f67-4&tab=files&file=verifier%2FBasin-Signal-Stage-Opening-Feedback-Pilot-Linux.tar.gz)
· [Oracle Game preview](https://www.oddish.app/tasks/swe-m2_game-development_battle-royale-opening-feedback-pilot-33a61f67?trial=swe-m2_game-development_battle-royale-opening-feedback-pilot-33a61f67-4&tab=game)
· [Sonnet control](https://www.oddish.app/experiments/5feb0797)
· [Sonnet with the replay](https://www.oddish.app/experiments/1f7e2f10)

The Oracle's 368,920,205-byte archive matched the saved SHA-256 receipt. In a
private WSL Vulkan window, **P** opened practice, all four slots filled, and
the keyboard replay deployed at Survey Camp with **F4** and completed a
round. Slot 2 won. The keyboard receipt is in the locally verified Oracle
release under `keyboard.GUxU2T1E/game/keyboard-playtest.json`. A separate
run through `play_wsl.sh --stage opening-pilot` selected the same archive
and completed a four-player round with ordinary input. Its Survey Camp
frame shows 100 health and 24 rounds after **E**. The launcher receipt and
frame are under `launcher.uXuVuiFQ` in the verified release. The Oracle's
Oddish Game capture built the project in Unreal 5.8.4, ran the preview map,
and published the rendered solo-practice menu and build archive.
Both L4 playback requests ended during machine startup without a player
link. The retry ended by 18:48:40 UTC. The verified release contains both
responses at `browser-playtest/transition-check.json` and
`browser-playtest-retry/playback-status.json`. The watcher now records this
end state when it follows a recent startup response for the same trial and
GPU.

Both pilot trials entered agent execution. The feedback trial's live trace
returned the supplied Relay Station note and recorded a separate Read call
for its PNG. The saved live result for the PNG is empty. Both development
logs recorded a round and rematch. Oddish cancelled both pilots and the
Stage 2 continuation at 18:18:25 UTC because quota was reached. None has a
verifier score or saved game project. The saved live feeds contain 495
control, 418 replay-feedback, and 5,022 continuation events. Oddish truncated
some tool inputs, including source file writes. The feeds and their hashes
are under `experiment/feedback-comparison/prebuilt-inputs/model-results/terminal-live`.
The comparison still needs both verifier scores and playable submissions.

The first Oracle ended during setup. Its hook expected the flat task to put
the starter under `/app`. The pinned Harbor Docker runner transfers
`environment/` into the configured working directory for prebuilt images
without a build recipe. Version 2 uses that layout and checks for the starter
under `/workspace`. Both bundles passed preflight and the local file-transfer
fixture. Oddish's registered control matched the new project and verifier
files. The gameplay verifier and the starter's contents match version 1.
[First setup failure](https://www.oddish.app/experiments/7d574325)
· [Pinned Harbor file delivery](https://github.com/abundant-ai/harbor/blob/0d84261622757bd9e2cf454d0f9e373b889df948/src/harbor/environments/base.py#L946)

The practice build alternates the first circle between the
road and the quarry. The player sees the next boundary and its direction
before it closes. The geometry check passed for both layouts. At the road
crossing, the south circle leaves 28.2 m of clearance and the north circle
leaves the crossing 8.2 m outside. At the covered trail crossing, the south
circle leaves the crossing 13.0 m outside and the north circle leaves 33.0 m
of clearance. These are geometric distances at the two crossings.

The runtime replay walks each route from the same Relay Station deployment
in both layouts. Three idle clients keep the lobby complete during this
comparison. The check uses the player's observed position and the circle
reported by the running game to calculate clearance. A separate practice
smoke run still exercises active opponents and a rematch.
[Route rotation Oracle](https://www.oddish.app/experiments/e1069683)

An opponent retains the last visible position for four seconds.
An opponent that loses sight searches there and scans when it arrives.
An imminent closure takes priority when the travel distance leaves little
time to reach safety. The C++ checks cover expiry, a fresh sighting, and
rotation timing. The combined Oracle verified a controlled search and
reacquisition in the packaged game.
[Opponent search Oracle](https://www.oddish.app/experiments/a28cfcee)

### Step 01 gameplay coverage

1. Use the verified Linux build as the reference for a repeatable two-client
   harness. Drive actions through normal game controls. Capture both clients'
   state at decision points and retain the build, scenario report, and logs.
2. Exercise movement ownership, opaque cover blocking view and shots, and the
   absence of opponent markers on either map. Drive a contested pickup and a
   contested driver seat, and check the single owner from both clients.
3. Check ammunition conservation on a cancelled reload and weapon switch,
   damage applied once for a valid hit, and zone damage on foot and in a
   vehicle. Exercise a single winner and a draw. Check that eliminated players
   lose their controls and that the rematch restores health, loot, vehicles,
   and zone state.
4. Run the [two-client playtest](#two-client-gameplay-verification) with
   rendering and sound enabled. Record both views of movement, occlusion,
   inventory, reload feedback, driving, and match results. Use the CPU
   headless run for repeatable rules checks and an interactive render-capable
   environment for presentation and frame-time observations.

Budget roughly one to two engineering days for the harness, three to five for
the core scenarios and fixes, and two to four for the first map and feedback
pass. Re-estimate after the first rendered playtest. These are planning ranges
for the game work.

### Verifier implementation plan

At each step, pass the declared project snapshot to a fresh separate verifier.
Exercise the new behaviors and repeat the earlier checks that still apply. Keep
the Linux startup smoke as a build gate. Put any required launch or automation
interface in the candidate instruction before a check depends on it.

| Step | Evidence to collect |
| --- | --- |
| 01 | Drive two clients through the gameplay scenarios above. Save the Linux package and both player views. Cover a combat win, a draw, and a clean rematch. |
| 02 | Traverse the road and covered foot routes from the playable starts. Check collision, reachable loot and vehicles, and synchronized current and preview boundaries through rounds with different final areas. Review rendered captures for map labels, movement, and feedback. |
| 03 | Exercise different deployments, same-area contention, and default placement. Check armor wear, damage and weapon-switch interruptions to healing, ammunition capacity, contested pickups, and a full reset across both clients. |
| 04 | Build the dedicated server and drive clients at the supported roster sizes. Exercise a departure during deployment, an active-round join attempt and disconnect, a win or draw, and a fresh round. Check contention and convergence on four clients with loopback and with added delay and packet loss, and record server timing. |

The reference has run through all four stages in Oddish. The candidate
continuation described below covers Stages 1–2. A standalone Stage 4 server
requires an Unreal image that can build and launch the Linux Server target.
[Epic dedicated-server setup](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-dedicated-servers-in-unreal-engine)

For behavioral scoring, save a named result for each scenario in the stage's
verifier report. Record skipped scenarios when an earlier startup check fails.
Eric's JAX Arena coverage run reports 19 checks in its first stage and 28 in its
second. The run's Oracle passed both stages and its no-op scored zero on the
same task version. An earlier model trial passed the first stage and scored
`0.852` on the second, with the failed checks available in the trial files.
[JAX coverage calibration](https://www.oddish.app/experiments/91cee07f)
· [JAX moving-geometry model run](https://www.oddish.app/experiments/95d976d6)

For browser play, check the Game tab's status and the capture manifest for a
build archive and successful map runs. The Unreal Ramen Shop runs include
individual verifier case reports and a separate Game capture. The save and
continue Oracle passed its verifier and its Game capture failed. A model run
passed the same verifier and captured Main Menu, Day 1, and Day 2.
[Ramen Shop trial and Game tab](https://www.oddish.app/tasks/ramen-shop-08-save-continue-23c2f79b?trial=ramen-shop-08-save-continue-23c2f79b-11)

### Reference playtest results

| Step | Verified on the Basin Signal reference | Open checks |
| --- | --- | --- |
| 01 | Two connected players agreed on contested loot and seat ownership, a stock wall blocking a shot, a clear hit, the winner, and a fresh round. The shooter saw the wall impact flash, and the wall hid it from the guest. Both viewports showed the draw after both players reached zero on the same zone tick. The rendered trials also covered inventory, reload, rifle audio, and the first rematch frame. Packaged checks covered recoil, fire cadence, empty-magazine feedback, a partial-reserve reload, and mounted zone damage. [Stock cover, impact, and draw](https://www.oddish.app/experiments/21e3da22) · [Rifle checks](https://www.oddish.app/experiments/b86d0f4d) · [Mounted zone](https://www.oddish.app/experiments/d8219db2) | — |
| 02 | Two clients agreed on the current and preview boundaries through ten warnings, with final areas at Relay Station and Survey Camp. The footpath and road checks passed headlessly and with both client views rendered on an NVIDIA A10. Both clients recorded the walk, takeoff, landing, and recovery poses and five audible movement and zone cues. [Zone](https://www.oddish.app/experiments/04a91aad) · [Routes](https://www.oddish.app/experiments/ff10f3fc) · [Movement and audio](https://www.oddish.app/experiments/c4015a4b) | — |
| 03 | Two players landed separately at Relay, and one defaulted to Survey on timeout. The equipment run checked capacity, interrupted and completed heals, and light armor. The heavy-armor run confirmed the last protected hit and the first unprotected hit. The four-player verifier also passed shared-area placement, timeout, and the full rematch reset. [Deployment and equipment](https://www.oddish.app/experiments/3c97e78a) · [Heavy armor](https://www.oddish.app/experiments/58f25934) · [Four-player rematch](https://www.oddish.app/experiments/073b77b1) | — |
| 04 | The cumulative reference passed all four steps, ending with eight dedicated Editor scenarios. These covered two-, three-, and four-player rosters, four-player delay and loss, lobby admission, deployment cancellation, replacement, a draw, and release and transfer of an occupied seat. [Four-step result](https://www.oddish.app/experiments/a80fadc7) | Packaged Linux clients passed the same eight scenarios against the dedicated Editor. The standalone Linux Server build still requires a Server-capable engine image. [Client package](https://www.oddish.app/experiments/6efb3d19) · [Server build probe](https://www.oddish.app/experiments/c96fbe37) |

## Packaging

From the repository root, build the draft archive with the shared development
environment.

```bash
uv run --frozen python tasks/swe-m2-game-developer/battle-royale/scripts/package_inputs.py
```

The script writes `experiment/dist/battle-royale-step1-draft.tar.gz`. The archive
preserves the step instruction, all linked component briefs and images, and the
runtime image recipe. Its manifest records the SHA-256 digest of every source
file. Harbor will mount the step's `workdir/` at `/app`, where the brief expects
the component files.

The [agent image recipe](environment/Dockerfile) pins the generic Unreal Engine
5.8.4 Linux base used by the
[Action Game Course trial](https://www.oddish.app/tasks/GD-RC-actiongamecourse-linux-a091a031?trial=GD-RC-actiongamecourse-linux-a091a031-12).
It prepares an agent-owned `/app` and gives the build user ownership of the
engine directories RunUAT uses for generated build files.
The runtime smoke checks read `Engine/Build/Build.version` from the running
image. Oddish game playback needs the built image and the saved Unreal project
artifact.

## Oddish baselines

Build the runnable calibration package from the repository root.

```bash
uv run --frozen python tasks/swe-m2-game-developer/battle-royale/scripts/package_baselines.py
```

The package is written to
`experiment/baselines/swe-m2_game-development_battle-royale/`. It follows the
one-step structure used by Eric Liu's JAX Arena Shooter. The step work directory
contains the game brief and its linked inputs. The Oracle supplies the editable
[Basin Signal project](steps/01-build-game/solution/project/) from the solution
directory. The submission contract is printed in the packaged instruction.
[JAX Arena Shooter baselines](https://www.oddish.app/experiments/5e06d91b)

Pass the full bundle directory to `oddish upload`. Oddish derives the
uploaded task name from the directory's final path component. Check the
returned task ID and version, then use both with `oddish run --task` and
`--version`.

The separate verifier collects `/workspace/submission` and records delivery,
Linux package, and map startup checks in `smoke.json`. The initial reward is
binary. A missing delivery or a failed build or launch scores `0`, and passing
all three checks scores `1`. Engine preparation and verifier infrastructure
errors leave the trial unscored. The two-client gameplay procedure below covers
behavior beyond this initial automatic score.

## Oddish model evaluation

The two-step continuation delivers the original briefs in order and carries
forward the model's editable project. For each stage, its verifier checks
Linux delivery, packaging, and map startup. The Game capture and reference
playtest reports provide evidence for manual gameplay review. The
continuation Oracle passed both stage reports on version 3, and the no-op
scored zero on both. Oddish cancelled the Claude Sonnet 5.5 Max continuation
because quota was reached. The attempt saved no score or game project.
[Continuation qualification](https://www.oddish.app/experiments/0eb84265)
· [Sonnet continuation](https://www.oddish.app/experiments/6ff13a55)

Stage the single-step package with Unreal build permissions for the model's
account.

```bash
uv run --frozen python tasks/swe-m2-game-developer/battle-royale/scripts/package_baselines.py --prepare-agent
```

This writes `experiment/model-ready/swe-m2_game-development_battle-royale/`.
Harbor prepares the Unreal cache directories in the agent container before
installing the agent. It checks the working directory, RunUAT, and the caches
as `agent` before model execution. Both containers use the pinned Unreal
image on CPU workers. The verifier still measures delivery, Linux packaging,
and map startup.

## Hackability assessment

The calibration package stages the public inputs and the Oracle in distinct
step directories. Harbor starts a separate verifier and transfers the declared
project artifact. The verifier runs the Unreal build and game as `ue` and
checks that this account cannot write the root-owned report directory.

The build and map startup checks establish the initial delivery baseline.
The map startup result depends on process logs. Trust in those logs for a
submission that intentionally misreports gameplay remains unassessed. A wider
gameplay score needs independent observations of both clients. The package
requests no outbound network access. Effective egress isolation on the worker
also remains unassessed.

## Build and launch smoke check

The [smoke image recipe](steps/01-build-game/tests/Dockerfile) uses the same
engine base. Inside a fresh container with networking disabled, mount the
submitted project read-only and provide a writable output location. The
following command runs as the image's unprivileged `ue` user.

```bash
python3 /tests/build_smoke.py \
  --project /submission/BattleRoyale.uproject \
  --output-dir /smoke/first-run
```

Pass the actual submitted project path. The smoke builds and packages the
project for Linux through RunUAT, then starts the package headlessly until
Unreal logs that it has loaded a map. The fresh output folder holds the packaged
game, build and launch logs, and a JSON report. This stage checks packaging and
startup. Two-client gameplay remains a separate verification milestone.
See [Epic's Linux packaging guide](https://dev.epicgames.com/documentation/unreal-engine/linux-development-quickstart-for-unreal-engine).

## Two-client gameplay verification

Build the submitted `.uproject` from its delivery instructions and launch two
separate packaged game processes with separate user profiles. For a listen
server, one player hosts and the other joins. For a dedicated server, launch the
server and both clients. Capture both player views and logs for the same match.
[Epic's multiplayer testing guide](https://dev.epicgames.com/documentation/unreal-engine/testing-multiplayer-in-unreal-engine)

1. Use the game's join and start flow. Check that both clients enter the same
   match and that each player's inputs control only their own character.
2. From both views, check that the opponent appears when visible and is
   occluded behind an opaque object. Check both maps for opponent markers.
3. Have both players attempt to collect the same item and then enter the same
   vehicle seat. Verify one owner or occupant at a time and consistent state
   across both clients. Check that combat results update both clients.
4. Observe the zone shrinking on both clients. Check the health effect on a
   player outside it and whether both clients see the same outcome.
5. Confirm the last player standing wins on both clients. Try moving and
   interacting after elimination, exercise the simultaneous-elimination draw,
   and start a rematch. Check that health, loot, vehicles, and the zone reset.

Record observed and unexercised cases alongside the build and runtime logs.

For a delivered listen-server game that supports command-line launch and join,
the [connection smoke](steps/01-build-game/tests/two_client_smoke.py) starts the
host first and records log evidence from both processes. Use the delivery's
packaged launchers, arguments, and literal log text for readiness and the
remote player's join. Repeat each argument option as needed.

```bash
python3 /tests/two_client_smoke.py \
  --host-launcher "$HOST_LAUNCHER" --host-arg="$HOST_ARG" \
  --client-launcher "$CLIENT_LAUNCHER" --client-arg="$CLIENT_ARG" \
  --host-ready-marker "$HOST_READY" \
  --host-connected-marker "$HOST_JOIN" \
  --client-connected-marker "$CLIENT_JOIN" \
  --output-dir "$NEW_OUTPUT_DIR"
```

Run the connection smoke as the container's `ue` user with the project's
supported headless arguments. It preserves both console logs and a JSON report
in the output directory. Use the gameplay procedure above to observe the
shared behavior in a match.

## Development log

### 2026-11-17

Added this task's development log while consolidating the repository layout.
The first-step instruction and component inputs are present; no task configuration,
environment, verifier, or oracle is present. The game was not built or evaluated
as part of this update. Runtime implementation and validation remain outstanding.

The repository source and documentation checks passed, including the dated-log
requirement for this draft.

Use a Git-ignored `experiment/` folder here for local experiments when needed.
Record their dated findings in this README and retain reproducible source files
outside the ignored folder when they become part of the task.

### 2026-11-18

Added a reproducible draft packager, the pinned Unreal Engine 5.8.4 recipe,
and an isolated Linux build and launch verifier. Local fixtures exercised
invalid inputs, failed builds, timeouts, and early exits. The pinned-image
permission probe confirmed RunUAT works as `agent` after preparing the
engine's writable directories. [Permission probe](https://www.oddish.app/experiments/3468a39f)

### 2026-11-19

The custom image passed its RunUAT check. Moved the playable Basin Signal
reference project and its delivery verifier into Step 01. The Linux build
passed a two-client match and rematch, and the reference verifier later
covered combat, contested interactions, and zone outcomes. The Stage 01
Sonnet submission also scored `1.0` on Linux delivery, build, and launch.
A replay built its exact saved project for the two-client match check.
[Custom image](https://www.oddish.app/experiments/15b0fc79)
· [Basin Signal verification](https://www.oddish.app/experiments/de2a0309)
· [Original Sonnet trial](https://www.oddish.app/experiments/d6669854)
· [Sonnet Linux replay](https://www.oddish.app/experiments/707f9bef)

### 2026-11-20

Verified Linux packages for the map and deployment milestones. The
four-stage reference passed eight dedicated Editor scenarios, including
four-player delay and loss, and the packaged clients passed the same
scenarios. The pinned image rejected the Linux Server target. A source-mode
probe reached compile action 736 of 949 before timing out and found missing
third-party source. The packaged dedicated server still needs a complete
source build or an approved Server-capable image.
[Stages 2 and 3 Linux packaging](https://www.oddish.app/experiments/7166aa9d)
· [Four-stage reference](https://www.oddish.app/experiments/a80fadc7)
· [Packaged clients](https://www.oddish.app/experiments/6efb3d19)
· [Server source probe](https://www.oddish.app/experiments/bdb5cf89)

The exact route-and-search release passed a keyboard-driven browser round
and rematch. In four controlled route replays from the same landing, the
road took 17.08 s and the trail 19.58 s. Health at the end of the first
shrink was 100 versus 82 in the south circle and 82 versus 100 in the north
circle. The separate contact replay confirmed search at the last visible
position and reacquisition after the player reappeared.
[Route-and-search release](https://www.oddish.app/experiments/d20a9ba3)
· [Contact replay](https://www.oddish.app/experiments/a28cfcee)

The opening-feedback Oracle scored `1.0` and completed a Linux keyboard
round. Both browser sessions ended during GPU startup. Oddish cancelled
the paired Sonnet pilots and the Stage 2 continuation when quota was
reached. They have no verifier scores or saved game projects. The local
event snapshots retain the available development traces.
[Opening Oracle](https://www.oddish.app/experiments/fd808ed0)
· [Control](https://www.oddish.app/experiments/5feb0797)
· [Replay feedback](https://www.oddish.app/experiments/1f7e2f10)
· [Stage 2 continuation](https://www.oddish.app/experiments/6ff13a55)

Added the WSL launcher mode for the saved Stage 01 Sonnet game. Both
software-rendered windows joined and accepted Ready. The private display
disconnected after the match started. Its lobby displayed about 2 FPS.

Detailed development notes and local run evidence are retained under
`experiment/`.
