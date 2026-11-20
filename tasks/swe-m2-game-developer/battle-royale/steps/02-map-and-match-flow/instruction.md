# Build out the survey basin

Continue the Unreal Engine 5 project from the first step. Give Basin Signal a
map that two players can learn and use to make decisions about where to loot,
when to move, and which route to take as the safe zone closes. Keep the code
highly modular so we can extend the game for later matches.

## Terrain and routes

- Build an original outdoor map with three recognizable landmarks. Include a
  relay station, a survey camp, and a quarry. Give each a distinct silhouette
  and name it on the in-game map so players can orient themselves.
- Connect two of the landmarks with a short, exposed road that a player can
  drive and a longer route on foot with usable cover. Make both routes easy
  to find from the landmarks.
- From either starting position, give each player an accessible route to
  weapons and ammunition. Place the vehicle where a player can reach the
  driver's seat and pull onto a road. Keep terrain and structures consistent
  with their collision so players, vehicles, and shots interact with the
  surfaces they can see.

## Match flow and feedback

- Give both players time to collect supplies before the first shrink and a
  chance to choose a route into the next safe area during each warning period.
  Support final safe areas around at least two different landmarks, with a
  walkable approach from either starting position. Keep each new safe area
  inside the preceding one and each final safe area on playable ground.
- During each warning, show the current and next safe-area boundaries together
  on the map. Make it clear which boundary applies now and when it will move.
  Both clients should display the same boundaries and countdown for the shared
  match. Apply zone damage outside the current boundary on foot and while
  driving.
- Make movement readable from both clients. Use animation that follows the
  character's movement and gives clear takeoff and landing feedback. Add
  movement and zone sounds that help players understand what is happening.
- Keep both players in the same match as opponents. Each controls their own
  character and sees the opponent when there is a clear line of sight in view.
  Keep opponent positions off the in-game map. Carry forward the first step's
  host and join flow, combat, inventory, vehicle, elimination, and rematch
  requirements on the updated map.

## Delivery

Update the editable project at `/workspace/submission/BattleRoyale.uproject`
and include the assets needed to build and play the revised map. Update
`/workspace/submission/README.md` with the Linux build and launch instructions,
the steps for hosting and joining a match, and the controls. Add a short map
guide that names the landmarks, describes the road and covered route, and
explains how the zone preview changes the route choice for two different final
areas.
