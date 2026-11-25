class_name VBCar
extends VehicleBody3D
## Godot's built-in VehicleBody3D (forward +Z) behind the same inputs as RaycastCar.

const MODELS := RaycastCar.MODELS
const WHEELS := [Vector3(0.78, 0.0, 1.35), Vector3(-0.78, 0.0, 1.35),
	Vector3(0.78, 0.0, -1.35), Vector3(-0.78, 0.0, -1.35)]
const SEATS := [Vector3(0.4, -0.15, -0.15), Vector3(-0.4, -0.15, -0.15),
	Vector3(0.4, -0.15, -1.0), Vector3(-0.4, -0.15, -1.0)]
## VehicleBody3D's brake is an impulse cap per wheel per physics step (N*s).
const BRAKE_IMPULSE_PER_N := 1.0 / 60.0 / 4.0

var impl := "vehicle_body"
var model := "sedan"
var in_throttle := 0.0
var in_brake := 0.0
var in_steer := 0.0
var in_handbrake := false
var in_reverse := false
var rev_hold := 0.0
var driver_kind := "none"
var occupants := {}
var wet := false
var wheelbase := 2.7
var max_steer := 0.55
var P := {}
var wheel_nodes: Array = []


func configure(p_model: String) -> void:
	model = p_model
	P = MODELS.get(p_model, MODELS["sedan"])
	mass = P["mass"]
	center_of_mass_mode = RigidBody3D.CENTER_OF_MASS_MODE_CUSTOM
	center_of_mass = Vector3(0, -0.1, 0)
	collision_layer = 2
	collision_mask = 1 | 2 | 4 | 16
	# the project default damping (0.1/s, combined) would act as ~2 kN of drag at 65 km/h
	linear_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	linear_damp = 0.0
	angular_damp_mode = RigidBody3D.DAMP_MODE_REPLACE
	angular_damp = 0.5
	continuous_cd = true
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = Vector3(1.8, 0.7, 4.4)
	cs.shape = sh
	cs.position = Vector3(0, 0.3, 0)
	add_child(cs)
	for i in range(4):
		var w := VehicleWheel3D.new()
		w.name = "Wheel%d" % i
		w.position = WHEELS[i]
		w.wheel_radius = 0.33
		w.wheel_rest_length = 0.35
		w.suspension_travel = 0.3
		w.suspension_stiffness = 9.8 / (4.0 * 0.12)
		w.damping_compression = 0.35 * 2.0 * sqrt(9.8 / (4.0 * 0.12) * 0.25)
		w.damping_relaxation = 0.45 * 2.0 * sqrt(9.8 / (4.0 * 0.12) * 0.25)
		w.suspension_max_force = 30000.0
		w.wheel_friction_slip = 1.0
		w.wheel_roll_influence = 0.3
		w.use_as_traction = i >= 2
		w.use_as_steering = i < 2
		add_child(w)
		wheel_nodes.append(w)


func fwd() -> Vector3:
	return global_basis.z


func left_dir() -> Vector3:
	return global_basis.x


func speed() -> float:
	return linear_velocity.dot(fwd())


func max_steer_at(v: float) -> float:
	return max_steer / (1.0 + absf(v) / 15.0)


func flat_local(p: Vector3) -> Vector2:
	var f := fwd()
	f.y = 0.0
	f = f.normalized()
	var d := p - global_position
	return Vector2(d.x * f.x + d.z * f.z, d.x * f.z - d.z * f.x)


func seat_xform(i: int) -> Transform3D:
	return global_transform * Transform3D(Basis(Vector3.UP, PI), SEATS[clampi(i, 0, 3)])


func _physics_process(_dt: float) -> void:
	if driver_kind == "player":
		CarInput.read_player(self)
	var vf := speed()
	var grip := 0.72 if wet else 1.0
	for w in wheel_nodes:
		w.wheel_friction_slip = grip
	var eng := 0.0
	if in_throttle > 0.0:
		eng = in_throttle * minf(P["force"], P["power"] / maxf(absf(vf), 0.5))
		if in_reverse:
			eng = -in_throttle * float(P["force"]) * 0.5
	engine_force = eng * 0.5
	# VehicleBody3D only scales the forward impulse by friction when a wheel also has a side
	# impulse, so straight-line braking ignores wheel_friction_slip: wet braking is applied here.
	var b: float = in_brake * float(P["brake"]) * BRAKE_IMPULSE_PER_N * (0.72 if wet else 1.0)
	if in_handbrake:
		b = maxf(b, float(P["brake"]) * 0.35 * BRAKE_IMPULSE_PER_N)
	brake = b
	steering = in_steer * max_steer_at(vf)
	var v := linear_velocity
	apply_central_force(-v * v.length() * float(P["drag"]) - fwd() * clampf(vf * 2.0, -1.0, 1.0) * 0.015 * mass * 9.8)
