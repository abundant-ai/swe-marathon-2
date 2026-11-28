extends Node3D
## Bodies with collision shapes, for the census shape read (census "shapes").
##
## Entity 1 (kind "vehicle") is a frozen RigidBody3D. After k ticks of the game it stands at
## ORIGIN + k * STEP, turned YAW + k * TURN degrees about +y, then ROLL degrees about +z. Its
## children, in tree order:
##   Body   a CollisionShape3D, a 1.8 x 1.4 x 4.4 box, at (0, 0.7, 0.1)
##   Nose   a CollisionShape3D, a 1.0 x 0.5 x 0.6 box, at (0, 0.4, -2.3), turned 10 degrees
##          about +y
##   Off    a CollisionShape3D, a box, disabled
##   Rack   a StaticBody3D with its own CollisionShape3D (another body's shape)
## Entity 2 (kind "npc") is a CharacterBody3D with a capsule (radius 0.3, height 1.7) at
## (0, 0.85, 0). Entity 3 (kind "vehicle") is a Node3D without shapes. The state report
## gives k.

const ORIGIN := Vector3(5.0, 0.2, -3.0)
const STEP := Vector3(0.2, 0.0, -0.1)
const YAW := 20.0
const TURN := 2.0
const ROLL := 4.0

var next_id := 1
var k := 0
var car: RigidBody3D = null


func _ready() -> void:
	DevConsole.world = self
	car = RigidBody3D.new()
	car.name = "Car"
	car.freeze = true
	car.freeze_mode = RigidBody3D.FREEZE_MODE_KINEMATIC
	car.transform = car_transform(0)
	_shape(car, "Body", Vector3(1.8, 1.4, 4.4), Transform3D(Basis(), Vector3(0, 0.7, 0.1)), false)
	_shape(car, "Nose", Vector3(1.0, 0.5, 0.6),
			Transform3D(Basis(Vector3.UP, deg_to_rad(10.0)), Vector3(0, 0.4, -2.3)), false)
	_shape(car, "Off", Vector3(3.0, 3.0, 3.0), Transform3D(), true)
	var rack := StaticBody3D.new()
	rack.name = "Rack"
	rack.position = Vector3(0, 1.6, 0)
	car.add_child(rack)
	_shape(rack, "RackShape", Vector3(1.0, 0.1, 1.5), Transform3D(), false)
	_register(car, "vehicle", "sedan")

	var walker := CharacterBody3D.new()
	walker.name = "Walker"
	walker.position = Vector3(-2.0, 0.0, 1.0)
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 1.7
	cs.shape = cap
	cs.position = Vector3(0, 0.85, 0)
	walker.add_child(cs)
	_register(walker, "npc", "office_worker")

	var sign := Node3D.new()
	sign.name = "Plain"
	sign.position = Vector3(3.0, 0.0, 3.0)
	_register(sign, "vehicle", "van")


func car_transform(ticks: int) -> Transform3D:
	var yaw := Basis(Vector3.UP, deg_to_rad(YAW + TURN * ticks))
	var roll := Basis(Vector3(0, 0, 1), deg_to_rad(ROLL))
	return Transform3D(yaw * roll, ORIGIN + STEP * ticks)


func _physics_process(_delta: float) -> void:
	k += 1
	car.global_transform = car_transform(k)


func _shape(parent: Node, shape_name: String, size: Vector3, xf: Transform3D, off: bool) -> void:
	var cs := CollisionShape3D.new()
	cs.name = shape_name
	var b := BoxShape3D.new()
	b.size = size
	cs.shape = b
	cs.transform = xf
	cs.disabled = off
	parent.add_child(cs)


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


func state_report() -> Dictionary:
	return {"ok": true, "k": k}
