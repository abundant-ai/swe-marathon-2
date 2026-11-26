extends Node3D
## Vehicles with seat markers, for the QA kit's seat reads and its body query.
##
## Entity 1 (kind "vehicle") is a frozen RigidBody3D (mass 1350, layer 2, mask 23). After k
## ticks of the game it stands at ORIGIN + k * STEP, turned YAW + k * TURN degrees about +y,
## then ROLL degrees about +z (its basis is Basis(+y) * Basis(+z)). Its nodes, in tree order:
##   Front          seat: index 1, door; no wheel
##   Driver         seat: index 0, door, wheel
##   Lamp           a Marker3D outside group "seat" (with index and door metadata)
##   Rear           a Node3D, offset and turned
##     RearLeft     seat: index 2.0 (a whole float); no door, no wheel
##     Bench        a Node3D, offset and turned
##       RearRight  seat: index 3, door as an array of three numbers, wheel a String
## Entity 2 (kind "vehicle") is a Node3D that stays put, turned with a little roll:
##   Driver         seat: index 0, door, wheel as an array of three numbers
##   Passenger      seat: no index, door an array of two numbers, wheel an array with a String
## Entity 3 (kind "npc") is a CharacterBody3D (layer 4, mask 7) with a Marker3D outside the
## group. A Marker3D in group "seat" right under this node belongs to no entity. The
## DevConsole's vehicle.spawn adds a Node3D vehicle with one seat. The state report gives k.

const ORIGIN := Vector3(12.0, 0.6, -7.0)
const STEP := Vector3(0.25, 0.01, -0.15)
const YAW := 35.0
const TURN := 1.5
const ROLL := 6.0

var next_id := 1
var k := 0
var car: RigidBody3D = null


func _ready() -> void:
	DevConsole.world = self
	car = RigidBody3D.new()
	car.name = "Car"
	car.freeze = true
	car.freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	car.mass = 1350.0
	car.collision_layer = 2
	car.collision_mask = 23
	car.transform = car_transform(0)
	_marker(car, "Front", Vector3(0.37, 0.5, -0.25), true,
			{"index": 1, "door": Vector3(0.95, 0.55, -0.25)})
	_marker(car, "Driver", Vector3(-0.37, 0.5, -0.25), true,
			{"index": 0, "door": Vector3(-0.95, 0.55, -0.25), "wheel": Vector3(-0.37, 0.95, -0.7)})
	_marker(car, "Lamp", Vector3(0.0, 1.2, -2.0), false,
			{"index": 7, "door": Vector3(0.0, 1.0, -2.2)})
	var rear := _node(car, "Rear", Vector3(0.05, 0.12, 0.85),
			Basis(Vector3.UP, deg_to_rad(30.0)) * Basis(Vector3.RIGHT, deg_to_rad(-8.0)))
	_marker(rear, "RearLeft", Vector3(-0.4, 0.1, 0.2), true, {"index": 2.0})
	var bench := _node(rear, "Bench", Vector3(0.5, 0.0, 0.1), Basis(Vector3.UP, deg_to_rad(-45.0)))
	_marker(bench, "RearRight", Vector3(0.1, 0.1, 0.0), true,
			{"index": 3, "door": [1, 0.55, 0.9], "wheel": "none"})
	_register(car, "vehicle", "sedan")

	var van := Node3D.new()
	van.name = "Van"
	van.transform = Transform3D(
			Basis(Vector3.UP, deg_to_rad(-110.0)) * Basis(Vector3(0, 0, 1), deg_to_rad(3.0)),
			Vector3(-6.0, 0.3, 4.0))
	_marker(van, "Driver", Vector3(-0.36, 0.48, -0.2), true,
			{"index": 0, "door": Vector3(-1.0, 0.6, 0.1), "wheel": [-0.36, 0.97, -0.62]})
	_marker(van, "Passenger", Vector3(0.36, 0.48, -0.2), true,
			{"door": [1.0, 0.6], "wheel": [0.3, "up", 0.2]})
	_register(van, "vehicle", "van")

	var walker := CharacterBody3D.new()
	walker.name = "Walker"
	walker.collision_layer = 4
	walker.collision_mask = 7
	walker.position = Vector3(2.0, 0.0, 3.0)
	_marker(walker, "Hand", Vector3(0.3, 1.0, 0.0), false, {"index": 0})
	_register(walker, "npc", "office_worker")

	_marker(self, "Stray", Vector3(1.0, 1.0, 1.0), true, {"index": 5, "door": Vector3.ZERO})


func car_transform(ticks: int) -> Transform3D:
	var yaw := Basis(Vector3.UP, deg_to_rad(YAW + TURN * ticks))
	var roll := Basis(Vector3(0, 0, 1), deg_to_rad(ROLL))
	return Transform3D(yaw * roll, ORIGIN + STEP * ticks)


func _physics_process(_delta: float) -> void:
	k += 1
	car.global_transform = car_transform(k)


func _register(node: Node3D, kind: String, archetype: String) -> int:
	var id := next_id
	next_id += 1
	node.add_to_group("entity")
	node.set_meta("entity_id", id)
	node.set_meta("kind", kind)
	node.set_meta("archetype", archetype)
	node.set_meta("faction", "civilian")
	add_child(node)
	return id


func _marker(parent: Node, marker_name: String, at: Vector3, seat: bool,
		values: Dictionary) -> Marker3D:
	var m := Marker3D.new()
	m.name = marker_name
	m.position = at
	if seat:
		m.add_to_group("seat")
	for key in values:
		m.set_meta(key, values[key])
	parent.add_child(m)
	return m


func _node(parent: Node, node_name: String, at: Vector3, turn: Basis) -> Node3D:
	var n := Node3D.new()
	n.name = node_name
	n.transform = Transform3D(turn, at)
	parent.add_child(n)
	return n


func spawn_vehicle(args: Dictionary) -> Dictionary:
	var at: Array = args.get("at", [0.0, 0.0, 0.0])
	var heading := float(args.get("heading", 0.0))
	var v := Node3D.new()
	v.name = "Spawned%d" % next_id
	v.transform = Transform3D(Basis(Vector3.UP, deg_to_rad(heading)),
			Vector3(float(at[0]), float(at[1]), float(at[2])))
	_marker(v, "Driver", Vector3(-0.35, 0.45, 0.0), true,
			{"index": 0, "door": Vector3(-0.9, 0.5, 0.0), "wheel": Vector3(-0.35, 0.9, -0.5)})
	return {"ok": true, "id": _register(v, "vehicle", "pickup")}


func state_report() -> Dictionary:
	return {"ok": true, "k": k}
