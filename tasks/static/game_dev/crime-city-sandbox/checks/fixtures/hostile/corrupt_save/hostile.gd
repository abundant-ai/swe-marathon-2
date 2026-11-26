extends Node
## Broken on purpose: loading a damaged save slot crashes the engine.
var world: Node


func on_damaged_save() -> void:
	OS.crash("damaged save")
