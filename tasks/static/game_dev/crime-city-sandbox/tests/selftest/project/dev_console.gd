extends Node
## Tiny Town's DevConsole (GDD chapter 17): exec(command, args) always answers
## {"ok": true, ...} or {"ok": false, "error": "..."}; events carry their tick.

signal event(name: String, data: Dictionary)

var world: Node = null


func exec(command: String, args: Dictionary = {}) -> Dictionary:
	if world == null:
		return {"ok": false, "error": "the world is not ready"}
	match command:
		"state":
			return world.state_report()
		"world.reset":
			return world.reset_world(args)
		"player.spawn":
			return world.spawn_player(args)
		"player.give":
			return world.give(args)
		"time.set":
			return world.set_time(args)
		"weather.set":
			return world.set_weather(args)
		"save":
			return world.save_slot(args)
		"load":
			return world.load_slot(args)
		"debug.stall":
			var ms = args.get("ms", 0)
			if typeof(ms) != TYPE_INT and typeof(ms) != TYPE_FLOAT:
				return {"ok": false, "error": "ms must be a number"}
			OS.delay_msec(clampi(int(ms), 0, 10000))
			return {"ok": true}
	return {"ok": false, "error": "unknown command: " + command}


func emit_event(name: String, data: Dictionary) -> void:
	data["tick"] = Engine.get_physics_frames()
	event.emit(name, data)
