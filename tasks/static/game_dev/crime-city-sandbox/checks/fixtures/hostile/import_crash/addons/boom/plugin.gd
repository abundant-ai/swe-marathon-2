@tool
extends EditorPlugin
## Broken on purpose: crashes the editor while the project imports.


func _enter_tree() -> void:
	OS.crash("deliberate import crash")
