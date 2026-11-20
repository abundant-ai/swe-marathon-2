# Basin Signal

Two players meet in an abandoned survey basin. Roads connect the depots,
houses, and vehicle spawns. Start a match together, collect supplies, and
stay inside the shrinking perimeter. The last player standing wins.

The editable Unreal Engine 5.8 project uses native C++ and engine primitives
for its original terrain, structures, vehicles, characters, and props.

## Build for Linux

Use Unreal Engine 5.8.4 with the Linux toolchain. Open `BattleRoyale.uproject`
in the editor or package it from this directory. Set `UE_ROOT` to the
installed engine directory.

```bash
"$UE_ROOT/Engine/Build/BatchFiles/RunUAT.sh" BuildCookRun \
  -project="$PWD/BattleRoyale.uproject" -platform=Linux \
  -clientconfig=Development -build -cook -stage -pak -archive \
  -archivedirectory="$PWD/Packaged" -unattended -noP4
```

## Host and join

In the packaged Linux directory, run `./BattleRoyale.sh -windowed` on both
players' computers. One player presses **F1** to host. The other presses
**F2** to join. For two processes on one computer, the default address is
`127.0.0.1:7777`. For a LAN session, start the joining player with
`-BRAddress=HOST_IP:7777` and replace `HOST_IP` with the host's address.
Each player presses **Enter** to ready up. After a result, both players can
press **Enter** again to start a fresh round.

| Input | Action |
| --- | --- |
| W, A, S, D | Move or drive |
| Mouse | Look and steer the view |
| Space | Jump on foot or brake in a vehicle |
| Left Shift | Sprint |
| E | Pick up nearby supplies or enter and exit a vehicle |
| 1, 2 | Equip an owned rifle |
| Left mouse | Fire |
| Right mouse | Aim |
| R | Reload |
| Tab | Toggle inventory |

## Game balance

These are fictional game settings. Each player starts with 100 health and
collects their own weapons and reserve ammunition. A rifle keeps its magazine
count when switched away. Reloading transfers compatible rounds on completion.

| Rifle | Mode | Magazine | Damage per hit | Minimum shot interval | Reload | Hip / sights spread | Hip recoil |
| --- | --- | --- | --- | --- | --- | --- | --- |
| AK-47 | Automatic | 18 | 24 | 0.15 s | 1.75 s | 2.00° / 0.45° | 1.30° |
| M16 | One shot per press | 24 | 17 | 0.25 s | 1.45 s | 1.25° / 0.25° | 0.65° |

Spread is the maximum angular deviation from the current aim. Recoil
accumulates up to 12° over repeated shots. Aiming down sights applies 73% of the hip
kick. After 0.28 seconds without a shot, the aim offset returns to zero over
the next 0.32 seconds. The perimeter starts at
80 metres and closes in stages. Time outside the perimeter costs nine health
per second, including while driving.

## Unattended two-client run

Launch the listen host with `"/Engine/Maps/Entry?listen"` as its map argument
and the second process with `127.0.0.1:7777` as its launch address. For headless
checking, pass `-NullRHI -NoSound -Unattended -BRAutoReady` to both processes.
The opt-in flag sends each player's normal ready action and records the match
state seen by that process, including the outcome and the fresh rematch.
