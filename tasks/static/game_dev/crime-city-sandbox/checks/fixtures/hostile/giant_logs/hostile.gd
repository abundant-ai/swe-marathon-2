extends Node
## Broken on purpose: prints about 1 MB every physics tick.
var world: Node
var line := "x".repeat(65536)


func _physics_process(_dt: float) -> void:
	for i in 16:
		print(line)
