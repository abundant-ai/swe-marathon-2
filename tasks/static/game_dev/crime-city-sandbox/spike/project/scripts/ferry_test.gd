class_name FerryTest
extends Node
## Item 9, second half: a ferry deck (AnimatableBody3D moved in _physics_process) carrying one
## parked car of each implementation. Reports each car's drift in deck coordinates.
## Profile: still 5 s, accelerate to 5 m/s over 10 s, cruise 30 s with a 10 s turn, slow down
## over 10 s, still 5 s.

var game: Node
var deck: AnimatableBody3D
var cars: Array = []
var start_local: Array = []
var n := 0
var x := 0.0
var v := 0.0
var yaw := 0.0
var samples: Array = []
var max_drift: Array = [0.0, 0.0]


static func start(g: Node) -> void:
	var f := FerryTest.new()
	f.name = "FerryTest"
	f.game = g
	g.main.add_child(f)
	f._build()


func _ready() -> void:
	process_physics_priority = -30


func _build() -> void:
	deck = AnimatableBody3D.new()
	deck.name = "FerryDeck"
	deck.sync_to_physics = true
	deck.collision_layer = 1
	var cs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(30, 1, 12)
	cs.shape = box
	deck.add_child(cs)
	deck.position = Vector3(0, 1.5, -900)
	game.dyn_root.add_child(deck)
	game.register(deck, "vehicle", "ferry", "city")
	var i := 0
	for impl in ["raycast", "vehicle_body"]:
		var p := deck.position + Vector3(-8.0 + 16.0 * i, 0.5 + 0.75, 0)
		var car = game.make_car("sedan", impl, p, Vector3(0, 0, -1), "civilian")
		car.driver_kind = "none"
		car.in_brake = 0.6
		car.in_handbrake = true
		cars.append(car)
		i += 1


func _physics_process(dt: float) -> void:
	n += 1
	var t := n / 60.0
	var a := 0.0
	if t >= 5.0 and t < 15.0:
		a = 0.5
	elif t >= 45.0 and t < 55.0:
		a = -0.5
	v = maxf(0.0, v + a * dt)
	var yaw_rate := 0.02 if (t >= 25.0 and t < 35.0) else 0.0
	yaw += yaw_rate * dt
	var fwd := Vector3(cos(yaw), 0, -sin(yaw))
	deck.global_transform = Transform3D(Basis(Vector3.UP, yaw), deck.global_position + fwd * v * dt)
	if n == 120:
		for c in cars:
			start_local.append(deck.global_transform.affine_inverse() * c.global_position)
	if n > 120:
		for k in range(cars.size()):
			var lp: Vector3 = deck.global_transform.affine_inverse() * cars[k].global_position
			var d := Vector2(lp.x - start_local[k].x, lp.z - start_local[k].z).length()
			max_drift[k] = maxf(max_drift[k], d)
		if n % 60 == 0:
			samples.append([snappedf(t, 0.1), snappedf(v, 0.01), snappedf(max_drift[0], 0.001), snappedf(max_drift[1], 0.001)])
	if n >= 3600:
		var res := {"max_drift_m": {"raycast": snappedf(max_drift[0], 0.001), "vehicle_body": snappedf(max_drift[1], 0.001)},
			"final_up": [cars[0].global_basis.y.y, cars[1].global_basis.y.y], "samples": samples,
			"ground_velocity_aware": game.args.get("ground_vel", "1") == "1"}
		print("FERRY_RESULT ", JSON.stringify(res))
		get_tree().quit(0)
