extends Node
## The DevConsole: "state" reports how many ticks the game has run (see main.gd).

signal event(name: String, data: Dictionary)

var world: Node = null


func exec(command: String, args: Dictionary = {}) -> Dictionary:
	if world == null:
		return {"ok": false, "error": "the world is not ready"}
	if command == "state" and args.is_empty():
		return world.state_report()
	return {"ok": false, "error": "unknown command: " + command}
