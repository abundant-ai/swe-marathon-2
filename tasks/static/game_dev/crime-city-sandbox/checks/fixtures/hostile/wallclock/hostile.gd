extends Node
## Broken on purpose: moves the people by the wall clock, so a replay at another pace differs.
var world: Node


func _physics_process(_dt: float) -> void:
	var w := Time.get_ticks_usec() / 1000000.0
	for n in world.npcs:
		n.position.x += sin(w * 7.0) * 0.01
