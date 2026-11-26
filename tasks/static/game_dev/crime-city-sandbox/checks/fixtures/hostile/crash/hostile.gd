extends Node
## Broken on purpose: the engine crashes at physics tick 10.
var world: Node


func _physics_process(_dt: float) -> void:
	if Engine.get_physics_frames() >= 10:
		OS.crash("deliberate crash")
