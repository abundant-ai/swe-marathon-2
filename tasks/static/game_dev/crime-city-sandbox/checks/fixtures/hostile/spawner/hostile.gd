extends Node
## Broken on purpose: starts 40 long-lived child processes per game process.
var world: Node
var started := 0


func on_reset() -> void:
	while started < 40:
		OS.create_process("/bin/sleep", ["4242"])
		started += 1
