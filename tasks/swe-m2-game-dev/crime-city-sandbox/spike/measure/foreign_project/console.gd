extends Node
signal event(name: String, data: Dictionary)
func exec(command: String, args: Dictionary = {}) -> Dictionary:
	match command:
		"state":
			var t = get_node("/root/Telemetry")
			return {"ok": true, "state": {"deltas": t.deltas.keys().map(func(k): return [k, t.deltas[k]]),
				"physics_frames": Engine.get_physics_frames(), "process_frames": Engine.get_process_frames()}}
		"arm.angle":
			get_tree().root.get_node("World").arm_speed = float(args.get("deg_per_tick", 1.0))
			return {"ok": true}
	return {"ok": false, "error": "unknown"}
