extends Node
## The DevConsole: "state" reports how many ticks the game has run (see main.gd);
## "vehicle.spawn" adds a vehicle with one seat at "at", turned "heading" degrees, and answers
## with its id.

signal event(name: String, data: Dictionary)

var world: Node = null


func exec(command: String, args: Dictionary = {}) -> Dictionary:
	if world == null:
		return {"ok": false, "error": "the world is not ready"}
	if command == "state":
		return world.state_report()
	if command == "vehicle.spawn":
		return world.spawn_vehicle(args)
	return {"ok": false, "error": "unknown command: " + command}
