extends Node
## Autoload "DevConsole": setup commands and the game's event stream (GDD chapter 17).

signal event(name: String, data: Dictionary)

var log_events := false


func emit_event(name: String, data: Dictionary) -> void:
	data["tick"] = Engine.get_physics_frames()
	if log_events:
		print("[event] ", name, " ", data)
	event.emit(name, data)


func _at(args: Dictionary, key := "at") -> Dictionary:
	var at = args.get(key)
	if at == null:
		return {}
	var ppos := Vector3.ZERO
	if Game.player != null and is_instance_valid(Game.player):
		ppos = Game.player.global_position
		if Game.player.vehicle != null:
			ppos = Game.player.vehicle.global_position
	var r := Game.plan.resolve(at, ppos)
	if r.is_empty():
		return {}
	if args.has("heading"):
		var h := deg_to_rad(float(args["heading"]))
		r["fwd"] = Vector3(sin(h), 0.0, -cos(h))
	return r


func exec(command: String, args: Dictionary = {}) -> Dictionary:
	if not Game.booted:
		return {"ok": false, "error": "not ready"}
	match command:
		"world.reset":
			return Game.world_reset(args)
		"state":
			return {"ok": true, "state": Game.state_report()}
		"time.set":
			var hm := String(args.get("hhmm", "12:00")).split(":")
			Game.clock_min = int(hm[0]) * 60 + int(hm[1])
			return {"ok": true}
		"weather.set":
			Game.weather = String(args.get("kind", "clear"))
			for c in get_tree().get_nodes_in_group("entity"):
				if c.get_meta("kind", "") == "vehicle":
					c.wet = Game.weather == "rain"
			return {"ok": true}
		"player.spawn":
			var r := _at(args)
			if r.is_empty():
				return {"ok": false, "error": "bad anchor"}
			var pos: Vector3 = r["pos"]
			var pl := Game.spawn_player(String(args.get("lead", "lead_a")), pos + Vector3(0, 0.05, 0), r["fwd"])
			return {"ok": true, "id": int(pl.get_meta("entity_id"))}
		"vehicle.spawn":
			var r2 := _at(args)
			if r2.is_empty():
				return {"ok": false, "error": "bad anchor"}
			var p2: Vector3 = r2["pos"]
			var f2: Vector3 = r2["fwd"]
			if String(args.get("at", "")) == "player" and Game.player != null:
				f2 = Game.player.forward()
				if args.has("heading"):
					f2 = r2["fwd"]
			Game.traffic.clear_zone(p2, 9.0)
			var impl := String(args.get("impl", Game.car_impl))
			var car = Game.make_car(String(args.get("model", "sedan")), impl, p2 + Vector3(0, 0.75, 0), f2,
				"police" if args.get("model", "") == "police" else "civilian")
			car.wet = Game.weather == "rain"
			if args.get("driver", "none") == "player" and Game.player != null:
				Game.player.enter_vehicle(car, 0)
				car.driver_kind = "player"
				emit_event("vehicle_entered", {"entity": int(Game.player.get_meta("entity_id")),
					"vehicle": int(car.get_meta("entity_id")), "seat": 0})
			return {"ok": true, "id": int(car.get_meta("entity_id"))}
		"npc.spawn":
			var r3 := _at(args)
			if r3.is_empty():
				return {"ok": false, "error": "bad anchor"}
			var arch := String(args.get("archetype", "civilian_0"))
			var fac := "police" if arch.begins_with("police") else "civilian"
			var pal: Dictionary = Game.POLICE_PALETTE if fac == "police" else Game.LEADS["lead_b"]
			var p3: Vector3 = r3["pos"]
			var npc := Game.make_person(arch, fac, pal, p3 + Vector3(0, 0.05, 0))
			npc.behaviour = String(args.get("behaviour", "idle"))
			npc.set_yaw(Person.yaw_of(r3["fwd"]))
			if args.has("face"):
				var fr: Dictionary = {}
				if args["face"] is String and Game.plan.junctions.has(args["face"]):
					fr = {"pos": Game.plan.junctions[args["face"]]["p"]}
				else:
					fr = Game.plan.resolve(args["face"])
				if not fr.is_empty():
					npc.face_point = fr["pos"]
			return {"ok": true, "id": int(npc.get_meta("entity_id"))}
		"prop.spawn":
			var r4 := _at(args)
			if r4.is_empty():
				return {"ok": false, "error": "bad anchor"}
			var size_a: Array = args.get("size", [2, 1, 1])
			var size := Vector3(float(size_a[0]), float(size_a[1]), float(size_a[2]))
			var p4: Vector3 = r4["pos"]
			var f4: Vector3 = r4["fwd"]
			var body := WorldBuilder._box(Game.dyn_root, "Prop_%d" % Game.next_id,
				p4 + Vector3(0, size.y * 0.5, 0), size, atan2(f4.x, f4.z), "prop",
				WorldBuilder._mat("prop", Color(0.8, 0.5, 0.1)), 16)
			var pid := Game.register(body, "prop", String(args.get("kind", "crate")), "none")
			return {"ok": true, "id": pid}
		"traffic.set":
			var d := float(args.get("density", 1.0))
			Game.traffic.reset(Game.seed_value, int(round(Game.plan.data["density"]["vehicles_base"] * d)),
				int(round(Game.plan.data["density"]["pedestrians_base"] * float(args.get("ped_density", d)))))
			return {"ok": true, "cars": Game.traffic.cars.size(), "peds": Game.traffic.peds.size()}
		"traffic.clear_zone":
			var r5 := _at(args)
			if r5.is_empty():
				return {"ok": false, "error": "bad anchor"}
			return {"ok": true, "removed": Game.traffic.clear_zone(r5["pos"], float(args.get("radius_m", 30.0)))}
		"car.impl":
			Game.car_impl = String(args.get("impl", "raycast"))
			return {"ok": true}
		_:
			return {"ok": false, "error": "unknown command " + command}
