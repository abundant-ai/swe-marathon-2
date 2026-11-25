class_name Traffic
extends Node
## Spawns seeded NPC cars on plan lanes and pedestrians on sidewalks, and keeps the lane
## occupancy that drivers use to find their leader.

var plan: Plan
var cars: Array = []
var peds: Array = []
var drivers: Array = []
var occ := {}
var density := 1.0
var ped_density := 1.0
var world_seed := 1


func _ready() -> void:
	process_physics_priority = -50


func reset(seed_value: int, car_count: int, ped_count: int) -> void:
	world_seed = seed_value
	for c in cars.duplicate():
		Game.despawn(c)
	for p in peds.duplicate():
		Game.despawn(p)
	cars.clear()
	peds.clear()
	drivers = drivers.filter(func(d): return is_instance_valid(d) and d.mode == "pursuit")
	var rng := RandomNumberGenerator.new()
	rng.seed = hash([seed_value, "traffic"])
	_spawn_cars(car_count, rng)
	_spawn_peds(ped_count, rng)


func _spawn_cars(n: int, rng: RandomNumberGenerator) -> void:
	var lanes: Array = plan.lane_ids
	var placed: Array = []
	var tries := 0
	while placed.size() < n and tries < n * 40:
		tries += 1
		var lid: String = lanes[rng.randi() % lanes.size()]
		var sg: Plan.Seg = plan.segs[lid]
		var s := rng.randf_range(6.0, sg.length - 12.0)
		var p := sg.point_at(s)
		var ok := true
		for q in placed:
			if q.distance_to(p) < 14.0:
				ok = false
				break
		if not ok:
			continue
		placed.append(p)
		var model: String = "taxi" if rng.randf() < 0.15 else "sedan"
		var car = Game.make_car(model, Game.car_impl, p + Vector3(0, 0.75, 0), sg.tangent_at(s), "civilian")
		car.driver_kind = "npc"
		var d := add_driver(car, "traffic")
		d.rng.seed = hash([world_seed, "driver", placed.size()])
		d.start_on(lid, s)
		cars.append(car)


func add_driver(car, mode: String) -> LaneDriver:
	var d := LaneDriver.new()
	d.name = "Driver"
	d.car = car
	d.plan = plan
	d.mode = mode
	car.add_child(d)
	drivers.append(d)
	return d


func _spawn_peds(n: int, rng: RandomNumberGenerator) -> void:
	if plan.sidewalks.is_empty():
		return
	for i in range(n):
		var sw: Dictionary = plan.sidewalks[i % plan.sidewalks.size()]
		var s := rng.randf_range(0.0, 400.0)
		var sp: Dictionary = plan.sidewalk_point(sw, s)
		var dir := 1.0 if rng.randf() < 0.5 else -1.0
		var p: Person = Game.make_person("civilian_%d" % (i % 4), "civilian", Game.palette_for(rng), sp["pos"])
		p.behaviour = "wander"
		p.ring = sw
		p.ring_s = s
		p.ring_dir = dir
		p.ring_lat = 0.7 * dir * rng.randf_range(0.6, 1.4)
		p.walk_speed = rng.randf_range(1.3, 1.6)
		p.set_yaw(Person.yaw_of(sp["fwd"] * dir))
		peds.append(p)


func clear_zone(center: Vector3, r: float) -> int:
	var n := 0
	for c in cars.duplicate():
		if is_instance_valid(c) and c.global_position.distance_to(center) < r:
			cars.erase(c)
			Game.despawn(c)
			n += 1
	return n


func _physics_process(_dt: float) -> void:
	occ.clear()
	var keep: Array = []
	for d in drivers:
		if not is_instance_valid(d) or d.path.is_empty():
			continue
		keep.append(d)
		var id: String = d.path[d.seg_i]
		if not occ.has(id):
			occ[id] = []
		occ[id].append([d.s, d])
	drivers = keep


## Returns Vector2(gap to the leader's rear bumper, leader speed), or (999, 0) if none.
func leader_gap(me: LaneDriver) -> Vector2:
	var acc := 0.0
	for k in range(me.seg_i, mini(me.path.size(), me.seg_i + 5)):
		var id: String = me.path[k]
		var best := INF
		var best_d = null
		if occ.has(id):
			for e in occ[id]:
				if e[1] == me:
					continue
				var es: float = e[0]
				if k == me.seg_i and es <= me.s:
					continue
				if es < best:
					best = es
					best_d = e[1]
		if best_d != null:
			var dist := acc + best - (me.s if k == me.seg_i else 0.0)
			return Vector2(dist - LaneDriver.CAR_LEN, best_d.car.speed())
		var sg: Plan.Seg = plan.segs[id]
		acc += sg.length - (me.s if k == me.seg_i else 0.0)
		if acc > 90.0:
			break
	return Vector2(999.0, 0.0)
