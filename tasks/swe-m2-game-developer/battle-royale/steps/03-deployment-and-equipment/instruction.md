# Choose where to deploy and what to carry

Continue the Basin Signal project in `/workspace/submission/`. Give each player
two decisions that shape the round. They should be able to choose where they
start and decide what to carry once they find supplies.

Keep the map changes and the two-human-player match flow from the previous
steps. Preserve movement, combat, weapon switching, reloading, driving, the
shrinking safe zone, elimination, win and draw results, and the rematch flow.

## Deployment

After the players ready up and before the round starts, let each player choose
from at least two deployment areas on the existing map. Show the choices on the
map. Give each area a distinct tradeoff. For example, an area near richer
supplies might have an exposed approach while another gives easier access to
cover. Keep each player's choice private.

Start the round when both players confirm or when a visible selection clock
expires. Choose and document the deadline and the default area for a player who
has yet to confirm. Spawn each player at a valid position in the assigned area.
If both choose the same area, use separate positions with room to move. Both
clients should enter the same active round and see a consistent round start.

## Equipment

- Add armor and healing supplies to the existing loot system. Provide two
  armor types with a choice between protection and backpack space while
  carried. Equipped armor reduces health loss from combat hits and wears down
  when it absorbs damage. At zero durability it stops protecting the player.
  Show its type and remaining durability. Zone damage still applies while
  wearing armor, including in a vehicle.
- Let injured players start a timed heal and show its progress. A completed
  heal restores health up to the normal maximum and consumes one supply.
  Taking damage or switching weapons during the action cancels it and leaves
  the supply available. A use attempt at full health or after elimination
  leaves health and inventory as they were.
- Give the backpack a finite capacity and show current usage, the limit, and
  the supplies it contains. Count reserve ammunition, healing supplies, and
  unequipped armor toward capacity. Preserve the two rifle slots and loaded
  magazine counts. Let players free space by dropping carried supplies. When
  a pickup exceeds the available capacity, leave the item in the world and
  tell the player why they could not collect it.
- When both players try to collect the same item, give it to at most one
  eligible player. Keep the remaining loot consistent across both clients and
  apply combat and healing outcomes consistently. On a rematch, offer a fresh
  deployment choice and reset the loot, armor, and backpack to their
  round-start state.

## Delivery

Update `/workspace/submission/BattleRoyale.uproject` and keep the source and
assets for the complete editable project in the same directory. Keep the code
highly modular. Update `/workspace/submission/README.md` with the Linux build,
host and join steps, and the controls for deployment and equipment. Document
the armor values and durability, the heal time and interruption rules, how
items and reserve ammunition count toward capacity, and the starting inventory.
