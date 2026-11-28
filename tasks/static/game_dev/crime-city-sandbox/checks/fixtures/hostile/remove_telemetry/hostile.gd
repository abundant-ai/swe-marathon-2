extends Node
## Broken on purpose: frees the first autoload (another node's) at physics tick 10.
var world: Node
var done := false


func _physics_process(_dt: float) -> void:
	if not done and Engine.get_physics_frames() >= 10:
		done = true
		get_tree().root.get_child(0).queue_free()
