extends Node
## Broken on purpose: the main thread spins forever from physics tick 10 on.
var world: Node


func _physics_process(_dt: float) -> void:
	if Engine.get_physics_frames() >= 10:
		while true:
			pass
