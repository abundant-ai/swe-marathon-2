extends Node
## Broken on purpose: allocates 8 MB more every physics tick from tick 10 on (at most 1.6 GB).
var world: Node
var hog := []


func _physics_process(_dt: float) -> void:
	if Engine.get_physics_frames() >= 10 and hog.size() < 200:
		var b := PackedByteArray()
		b.resize(8 << 20)
		b.fill(7)
		hog.append(b)
