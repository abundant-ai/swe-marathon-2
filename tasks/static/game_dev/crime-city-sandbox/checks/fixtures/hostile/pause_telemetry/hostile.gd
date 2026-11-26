extends Node
## Broken on purpose: turns off the first autoload's processing at physics tick 10.
var world: Node
var done := false


func _physics_process(_dt: float) -> void:
	if not done and Engine.get_physics_frames() >= 10:
		done = true
		var first := get_tree().root.get_child(0)
		first.set_physics_process_internal(false)
		first.set_physics_process(false)
		first.set_process_internal(false)
