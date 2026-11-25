extends Node
## Autoload "Game": roles, world state, the entity registry and spawning.

const LEADS := {
	"lead_a": {"skin": Color(0.85, 0.68, 0.52), "shirt": Color(0.75, 0.2, 0.2), "pants": Color(0.15, 0.15, 0.25), "shoes": Color(0.1, 0.1, 0.1)},
	"lead_b": {"skin": Color(0.45, 0.3, 0.2), "shirt": Color(0.2, 0.55, 0.3), "pants": Color(0.3, 0.25, 0.2), "shoes": Color(0.2, 0.1, 0.05)},
	"lead_c": {"skin": Color(0.95, 0.8, 0.7), "shirt": Color(0.9, 0.8, 0.2), "pants": Color(0.1, 0.1, 0.1), "shoes": Color(0.9, 0.9, 0.9)},
}
const POLICE_PALETTE := {"skin": Color(0.7, 0.55, 0.4), "shirt": Color(0.1, 0.15, 0.4), "pants": Color(0.08, 0.1, 0.25), "shoes": Color(0.05, 0.05, 0.05)}

var args := {}
var role := "solo"
var seed_value := 1
var map_name := "downtown"
var plan: Plan
var main: Node3D
var static_root: Node3D
var dyn_root: Node3D
var traffic: Traffic
var signals: SignalSystem
var wanted: WantedSystem
var camera: Camera3D
var hud: CanvasLayer
var player: Person = null
var next_id := 1
var next_static_id := 900000
var weather := "clear"
var clock_min := 720.0
var car_impl := "raycast"
var art := "primitive"
var booted := false
var boot_ms := 0.0
var last_reset_ms := 0.0


func _ready() -> void:
	process_physics_priority = -100
	for a in OS.get_cmdline_user_args():
		if a.begins_with("--"):
			var kv := a.substr(2).split("=", true, 1)
			args[kv[0]] = kv[1] if kv.size() > 1 else "true"
	role = args.get("role", "solo")
	seed_value = int(args.get("seed", "1"))
	map_name = args.get("map", "downtown")
	car_impl = args.get("car", "raycast")
	art = args.get("art", "primitive")


func boot(main_node: Node3D) -> void:
	var t0 := Time.get_ticks_usec()
	main = main_node
	var plan_dir: String = args.get("plan-dir", "res://design/plan")
	plan = Plan.load_file(plan_dir.path_join("downtown_block.json"))
	static_root = Node3D.new()
	static_root.name = "World"
	main.add_child(static_root)
	WorldBuilder.build(plan, static_root)
	for l in get_tree().get_nodes_in_group("street_light"):
		register_static(l, "light", "street_light", "city")
	dyn_root = Node3D.new()
	dyn_root.name = "Dynamic"
	main.add_child(dyn_root)
	signals = SignalSystem.new()
	signals.name = "Signals"
	main.add_child(signals)
	signals.setup(plan)
	traffic = Traffic.new()
	traffic.name = "Traffic"
	traffic.plan = plan
	main.add_child(traffic)
	wanted = WantedSystem.new()
	wanted.name = "Wanted"
	main.add_child(wanted)
	camera = Camera3D.new()
	camera.name = "Camera"
	camera.fov = 70.0
	main.add_child(camera)
	camera.current = true
	var rig := CameraRig.new()
	rig.name = "CameraRig"
	main.add_child(rig)
	hud = Hud.build()
	main.add_child(hud)
	booted = true
	boot_ms = (Time.get_ticks_usec() - t0) / 1000.0
	match role:
		"solo":
			world_reset({"seed": seed_value})
		"bench":
			Bench.start(self)
		"ferry":
			world_reset({"seed": seed_value, "density": 0.0})
			FerryTest.start(self)
		"server", "client", "nettest":
			NetRoles.start(role, self)
		_:
			world_reset({"seed": seed_value})


# ---------------------------------------------------------------- registry

func register(node: Node, kind: String, archetype: String, faction: String) -> int:
	var id := next_id
	next_id += 1
	_tag(node, id, kind, archetype, faction)
	return id


func register_static(node: Node, kind: String, archetype: String, faction: String, _tag2 := "") -> int:
	var id := next_static_id
	next_static_id += 1
	_tag(node, id, kind, archetype, faction)
	return id


func _tag(node: Node, id: int, kind: String, archetype: String, faction: String) -> void:
	node.set_meta("entity_id", id)
	node.set_meta("kind", kind)
	node.set_meta("archetype", archetype)
	node.set_meta("faction", faction)
	node.add_to_group("entity")


func despawn(node) -> void:
	if node == null or not is_instance_valid(node):
		return
	if node is Person and node.vehicle != null:
		node.vehicle = null
	if node.has_method("seat_xform"):
		for k in node.occupants:
			var o = node.occupants[k]
			if is_instance_valid(o) and o != player:
				despawn(o)
			elif o == player:
				player.vehicle = null
				player.collision_layer = 4
				player.collision_mask = 1 | 2 | 4 | 16
	for c in node.find_children("*", "", true, false):
		if c.is_in_group("entity"):
			c.remove_from_group("entity")
	node.remove_from_group("entity")
	node.queue_free()


func entity_by_id(id: int) -> Node:
	for e in get_tree().get_nodes_in_group("entity"):
		if int(e.get_meta("entity_id", -1)) == id:
			return e
	return null


# ---------------------------------------------------------------- spawning

func palette_for(rng: RandomNumberGenerator) -> Dictionary:
	return {"skin": Color.from_hsv(0.07, rng.randf_range(0.3, 0.6), rng.randf_range(0.35, 0.95)),
		"shirt": Color.from_hsv(rng.randf(), rng.randf_range(0.3, 0.9), rng.randf_range(0.3, 0.9)),
		"pants": Color.from_hsv(rng.randf(), rng.randf_range(0.1, 0.6), rng.randf_range(0.1, 0.5)),
		"shoes": Color(0.1, 0.08, 0.06)}


func make_person(archetype: String, faction: String, palette: Dictionary, pos: Vector3) -> Person:
	var p := Person.new()
	p.name = "P_%d" % next_id
	p.setup(archetype, faction, palette, art)
	dyn_root.add_child(p)
	p.global_position = pos
	register(p, "npc", archetype, faction)
	return p


func make_car(model: String, impl: String, pos: Vector3, fwd: Vector3, faction: String) -> Node3D:
	var car
	var f := Vector3(fwd.x, 0.0, fwd.z).normalized()
	var basis: Basis
	if impl == "vehicle_body":
		car = VBCar.new()
		basis = Basis.looking_at(-f, Vector3.UP)
	else:
		car = RaycastCar.new()
		basis = Basis.looking_at(f, Vector3.UP)
	car.name = "Car_%d" % next_id
	car.configure(model)
	CarVisual.attach(car, model, impl)
	car.transform = Transform3D(basis, pos)
	dyn_root.add_child(car)
	register(car, "vehicle", "police_car" if model == "police" else model, faction)
	return car


func spawn_player(lead: String, pos: Vector3, fwd: Vector3) -> Person:
	if player == null or not is_instance_valid(player):
		player = Person.new()
		player.name = "Player"
		player.is_player = true
		player.lead = lead
		player.setup("lead", "player", LEADS.get(lead, LEADS["lead_a"]), art)
		player.behaviour = "player"
		dyn_root.add_child(player)
		register(player, "player", lead, "player")
	elif player.vehicle != null:
		player.exit_vehicle()
	player.global_position = pos
	player.velocity = Vector3.ZERO
	player.set_yaw(Person.yaw_of(fwd))
	player.cam_yaw = player.yaw
	DevConsole.emit_event("teleport", {"entity": int(player.get_meta("entity_id")), "reason": "setup"})
	return player


# ---------------------------------------------------------------- world reset

func world_reset(a: Dictionary) -> Dictionary:
	var t0 := Time.get_ticks_usec()
	seed_value = int(a.get("seed", seed_value))
	for c in dyn_root.get_children():
		despawn(c)
		dyn_root.remove_child(c)
	player = null
	next_id = 1
	traffic.drivers.clear()
	signals.reset()
	wanted.reset()
	weather = "clear"
	clock_min = 720.0
	var d := float(a.get("density", 1.0))
	traffic.cars.clear()
	traffic.peds.clear()
	var home: Dictionary = plan.pois.get("safehouse_a", {})
	spawn_player("lead_a", home.get("pos", Vector3(0, 0.2, 0)), Vector3(0, 0, -1))
	traffic.reset(seed_value, int(round(plan.data["density"]["vehicles_base"] * d)),
		int(round(plan.data["density"]["pedestrians_base"] * float(a.get("ped_density", d)))))
	hud_update()
	last_reset_ms = (Time.get_ticks_usec() - t0) / 1000.0
	return {"ok": true, "ms": last_reset_ms}


func hud_update() -> void:
	if hud != null:
		Hud.set_wanted(hud, wanted.level)


func state_report() -> Dictionary:
	var pl := {}
	if player != null and is_instance_valid(player):
		pl = {"id": int(player.get_meta("entity_id")), "lead": player.lead, "health": player.health,
			"armour": 0, "money": 0, "wanted": wanted.level,
			"vehicle": int(player.vehicle.get_meta("entity_id")) if player.vehicle != null else null,
			"seat": player.seat if player.vehicle != null else null}
	return {"tick": Engine.get_physics_frames(), "map": map_name, "clock": clock_min,
		"weather": weather, "player": pl, "wanted": wanted.level,
		"network": {"role": role, "peers": 0}, "ui": {"phone": false, "map": false, "paused": false}}
