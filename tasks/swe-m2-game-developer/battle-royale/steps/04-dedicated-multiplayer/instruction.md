# Run the game on a dedicated server

Extend the Unreal project in `/workspace/submission` so that two to four human
opponents can play on a dedicated Linux server. The server should run without a
local player or graphical window. Keep the existing map, deployment choices,
equipment, vehicles, and shrinking zone. The dedicated server replaces
player-hosted sessions for this delivery.

## Joining and starting a round

- Let the operator configure the listening port and the number of players per
  round, from two to four. Use four players by default and document how to
  select a smaller match.
- Let players connect to the server by address and port. Show the connected
  players and who is ready. Start deployment once the configured number of
  players is connected and ready. Apply the previous deployment rules to the
  whole roster, including separate positions within a shared area and default
  placement when the timer expires.
- Decline joins while the lobby is full or a round is underway and tell the
  player why. A player who leaves the lobby frees a slot for someone else. If a
  player leaves during deployment, return everyone to the lobby and accept a
  replacement before starting deployment again.

## Match rules

- Each player controls only their own character. Resolve deployment, combat,
  item ownership, vehicle occupancy, and zone damage on the server. Keep the
  results consistent across the clients. Preserve cover and keep opponent
  locations off the map.
- A player who disconnects during a round is eliminated when the server detects
  the disconnect. Release any vehicle seat they occupied. Apply the usual
  elimination rules to each character whose health reaches zero.
- The last surviving player wins. If the server eliminates the final survivors
  together, the round ends in a draw. Show the same result to every connected
  player.
- After a result, let players ready up for another round on the same server.
  Fill open slots from the lobby and reset health, deployment choices,
  equipment, loot, vehicles, and the safe zone for the new round.

## Four-player playtest

Run a match with four separate clients on a local network or loopback. Repeat
under a development network profile with approximately 80 ms of additional
round-trip delay and 1% packet loss. Include two players going for the same
item or driver seat, then have one active player disconnect. The connected
players should see one owner or occupant and finish the match with the same
result. Start a new round on the same server and check that the lobby admits
a replacement.

## Delivery

Update `/workspace/submission/BattleRoyale.uproject` and keep the code highly
modular. In `/workspace/submission/README.md`, give the instructions for
building and launching the Linux server and client, configuring the number of
players and port, connecting to the server, and starting a rematch. Record the
machine and network setup, how to reproduce both playtest conditions, server
frame times, and any limits you encountered.
