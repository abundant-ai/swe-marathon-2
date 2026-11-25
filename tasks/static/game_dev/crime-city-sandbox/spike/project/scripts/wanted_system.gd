class_name WantedSystem
extends Node
## Crimes, witnesses and the wanted level, plus police dispatch from stations.
## Spike scope: running a red light is the only crime; level 1 sends one car.

const WITNESS_RANGE := {"clear": 80.0, "overcast": 70.0, "rain": 50.0, "fog": 30.0}
const UNITS_BY_LEVEL := [0, 1, 2, 3, 4, 5]
const MIN_ORIGIN_M := 100.0

var level := 0
var units: Array = []
var _prev := {}
var _ray := PhysicsRayQueryParameters3D.new()


func _ready() -> void:
	process_physics_priority = -10
	_ray.collision_mask = 1


func reset() -> void:
	level = 0
	units.clear()
	_prev.clear()


func _physics_process(_dt: float) -> void:
	var pl: Person = Game.player
	if pl == null or not is_instance_valid(pl):
		return
	if pl.vehicle != null and is_instance_valid(pl.vehicle) and pl.seat == 0:
		_check_red_light(pl.vehicle)
	units = units.filter(func(u): return is_instance_valid(u))


func _check_red_light(car) -> void:
	var p: Vector3 = car.global_position
	var key: int = car.get_instance_id()
	if _prev.has(key):
		var p0: Vector3 = _prev[key]
		for ap in Game.plan.signalised_approaches_near(p, 30.0):
			var sp: Vector3 = ap["stop_p"]
			var f: Vector3 = ap["fwd"]
			var d0 := (p0 - sp).dot(f)
			var d1 := (p - sp).dot(f)
			if d0 < 0.0 and d1 >= 0.0:
				var lat := (p - sp).dot(ap["right"])
				if lat >= -0.5 and lat <= float(ap["half_w"]) + 0.5:
					if Game.signals.state(ap["id"]) == "red":
						crime("ran_red_light", car, {"approach": ap["id"], "junction": ap["junction"]})
	_prev[key] = p


func witnesses_of(target: Node3D) -> Array:
	var out: Array = []
	var rng: float = WITNESS_RANGE.get(Game.weather, 80.0)
	var tp := target.global_position + Vector3(0, 0.8, 0)
	var space := target.get_world_3d().direct_space_state
	for e in get_tree().get_nodes_in_group("entity"):
		if e.get_meta("faction", "") != "police" or e == target:
			continue
		var k: String = e.get_meta("kind", "")
		if k != "npc" and k != "vehicle":
			continue
		var eye: Vector3 = e.global_position + Vector3(0, 1.65 if k == "npc" else 1.2, 0)
		if eye.distance_to(tp) > rng:
			continue
		_ray.from = eye
		_ray.to = tp
		var hit := space.intersect_ray(_ray)
		if hit.is_empty():
			out.append(int(e.get_meta("entity_id")))
	return out


func crime(kind: String, target: Node3D, data: Dictionary) -> void:
	var w := witnesses_of(target)
	data["kind"] = kind
	data["witnessed"] = not w.is_empty()
	data["witnesses"] = w
	data["at"] = [target.global_position.x, target.global_position.y, target.global_position.z]
	DevConsole.emit_event("crime", data)
	if w.is_empty():
		return
	var new_level := maxi(level, 1)
	if new_level != level:
		level = new_level
		DevConsole.emit_event("wanted_changed", {"level": level, "cause": kind})
		Game.hud_update()
		_dispatch(UNITS_BY_LEVEL[level] - units.size())


func _dispatch(n: int) -> void:
	var pl: Person = Game.player
	var ppos := pl.global_position
	var cam := Game.camera
	var stations: Array = []
	for id in Game.plan.pois:
		var poi: Dictionary = Game.plan.pois[id]
		if poi["kind"] != "police_station" or not poi.has("exit"):
			continue
		var ex := Game.plan.resolve(poi["exit"])
		var sp: Vector3 = ex["pos"]
		var dist := Vector2(sp.x - ppos.x, sp.z - ppos.z).length()
		var seen := cam != null and cam.is_position_in_frustum(sp + Vector3(0, 1, 0))
		stations.append({"id": id, "exit": poi["exit"], "pos": sp, "fwd": ex["fwd"], "dist": dist, "seen": seen})
	stations.sort_custom(func(a, b): return a["dist"] < b["dist"])
	for i in range(n):
		var chosen = null
		for st in stations:
			if st["dist"] >= MIN_ORIGIN_M and not st["seen"]:
				chosen = st
				break
		if chosen == null:
			DevConsole.emit_event("police_dispatch_failed", {"reason": "no station out of view and 100 m away"})
			return
		var spawn_pos: Vector3 = chosen["pos"] + chosen["fwd"] * (i * 9.0)
		var car = Game.make_car("police", Game.car_impl, spawn_pos + Vector3(0, 0.75, 0), chosen["fwd"], "police")
		car.driver_kind = "police"
		var d := Game.traffic.add_driver(car, "pursuit")
		d.obey_signals = false
		d.v_limit = 19.4
		d.target = pl
		d.start_on(chosen["exit"]["lane"], float(chosen["exit"]["s"]) + i * 9.0)
		units.append(car)
		DevConsole.emit_event("police_dispatched", {"unit": int(car.get_meta("entity_id")),
			"station": chosen["id"], "origin": [spawn_pos.x, spawn_pos.y, spawn_pos.z], "level": level})
