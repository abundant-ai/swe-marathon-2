extends Node
# The project's own autoload (unrelated to QA); it records the physics delta it sees.
var deltas := {}
func _physics_process(dt: float) -> void:
	deltas[dt] = deltas.get(dt, 0) + 1
