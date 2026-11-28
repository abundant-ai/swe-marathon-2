extends Node
## The DevConsole: "state" reports the angles the game used last (see main.gd).

signal event(name: String, data: Dictionary)

var world: Node = null


func exec(command: String, _args: Dictionary = {}) -> Dictionary:
	if world == null:
		return {"ok": false, "error": "the world is not ready"}
	if command == "state":
		return world.state_report()
	return {"ok": false, "error": "unknown command: " + command}
