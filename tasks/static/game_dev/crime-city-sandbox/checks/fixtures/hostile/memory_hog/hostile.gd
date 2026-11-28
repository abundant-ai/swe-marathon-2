extends Node
## Broken on purpose: from physics tick 8 allocates 96 MB more every tick (at most 768 MB).
var world: Node
var hog := []


func _physics_process(_dt: float) -> void:
	if Engine.get_physics_frames() >= 8 and hog.size() < 8:
		var b := PackedByteArray()
		b.resize(96 << 20)
		b.fill(7)
		hog.append(b)
