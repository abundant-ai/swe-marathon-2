class_name RaycastCar
extends RigidBody3D
## Custom raycast car on Jolt: four suspension rays (spring-damper), slip-angle tyres with a
## friction circle, rear-wheel drive with a power limit, brakes that never reverse the wheel,
## aerodynamic drag. Forward is -Z. Inputs: in_throttle, in_brake, in_steer (+left), in_reverse.

const MODELS := {
	"sedan": {"mass": 1300.0, "force": 4600.0, "power": 60000.0, "brake": 11000.0, "drag": 0.40},
	"police": {"mass": 1450.0, "force": 6200.0, "power": 110000.0, "brake": 12500.0, "drag": 0.40},
	"taxi": {"mass": 1350.0, "force": 4600.0, "power": 60000.0, "brake": 11000.0, "drag": 0.42},
}
const WHEELS := [Vector3(-0.78, 0.0, -1.35), Vector3(0.78, 0.0, -1.35),
	Vector3(-0.78, 0.0, 1.35), Vector3(0.78, 0.0, 1.35)]
const SEATS := [Vector3(-0.4, -0.15, 0.15), Vector3(0.4, -0.15, 0.15),
	Vector3(-0.4, -0.15, 1.0), Vector3(0.4, -0.15, 1.0)]

var impl := "raycast"
var model := "sedan"
var in_throttle := 0.0
var in_brake := 0.0
var in_steer := 0.0
var in_handbrake := false
var in_reverse := false
var rev_hold := 0.0
var driver_kind := "none"      # player | npc | police | none
var occupants := {}
var wet := false
var wheelbase := 2.7
var max_steer := 0.55
var rest := 0.35
var radius := 0.33
var k_spring := 0.0
var c_damp := 0.0
var c_alpha := 50000.0
var mu := 1.0
var P := {}
var contacts := 0
var ground_velocity_aware := true
var _q := PhysicsRayQueryParameters3D.new()


func configure(p_model: String) -> void:
	model = p_model
	P = MODELS.get(p_model, MODELS["sedan"])
	mass = P["mass"]
	var static_load: float = mass * 9.8 / 4.0
	k_spring = static_load / 0.12
	c_damp = 2.0 * 0.35 * sqrt(k_spring * mass / 4.0)
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


func _ready() -> void:
	ground_velocity_aware = Game.args.get("ground_vel", "1") == "1"
	_q.collision_mask = 1
	_q.exclude = [get_rid()]


func fwd() -> Vector3:
	return -global_basis.z


func left_dir() -> Vector3:
	return -global_basis.x


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
	return global_transform * Transform3D(Basis.IDENTITY, SEATS[clampi(i, 0, 3)])


func _physics_process(dt: float) -> void:
	if driver_kind == "player":
		CarInput.read_player(self)
	var st := get_world_3d().direct_space_state
	var xf := global_transform
	var up := xf.basis.y
	var f := -xf.basis.z
	var v := linear_velocity
	var vf_body := v.dot(f)
	var steer_a := in_steer * max_steer_at(vf_body)
	var eng := 0.0
	if in_throttle > 0.0:
		eng = in_throttle * minf(P["force"], P["power"] / maxf(absf(vf_body), 0.5))
		if in_reverse:
			eng = -in_throttle * P["force"] * 0.5
	var m_share := mass * 0.25
	var grip := mu * (0.72 if wet else 1.0)
	contacts = 0
	for i in range(4):
		var mount: Vector3 = xf * WHEELS[i]
		_q.from = mount
		_q.to = mount - up * (rest + radius)
		var hit := st.intersect_ray(_q)
		if hit.is_empty():
			continue
		contacts += 1
		var hp: Vector3 = hit["position"]
		var n: Vector3 = hit["normal"]
		var comp := rest - (mount.distance_to(hp) - radius)
		var r := hp - global_position
		var vp := v + angular_velocity.cross(r)
		# moving ground (ferry deck, another vehicle): tyre forces work on the relative velocity
		if ground_velocity_aware and hit["collider"] is PhysicsBody3D and not (hit["collider"] is StaticBody3D and not hit["collider"] is AnimatableBody3D):
			var grid: RID = hit["rid"]
			var gl: Vector3 = PhysicsServer3D.body_get_state(grid, PhysicsServer3D.BODY_STATE_LINEAR_VELOCITY)
			var ga: Vector3 = PhysicsServer3D.body_get_state(grid, PhysicsServer3D.BODY_STATE_ANGULAR_VELOCITY)
			var gxf: Transform3D = PhysicsServer3D.body_get_state(grid, PhysicsServer3D.BODY_STATE_TRANSFORM)
			vp -= gl + ga.cross(hp - gxf.origin)
		var fz := k_spring * comp - c_damp * vp.dot(up)
		if fz <= 0.0:
			continue
		var wf := f
		if i < 2:
			wf = f.rotated(up, steer_a)
		wf = (wf - n * wf.dot(n)).normalized()
		var ws := n.cross(wf).normalized()
		var vwf := vp.dot(wf)
		var vws := vp.dot(ws)
		var fl := 0.0
		if i >= 2:
			fl += eng * 0.5
		var bmax: float = in_brake * float(P["brake"]) * (0.3 if i < 2 else 0.2)
		if in_handbrake and i >= 2:
			bmax = maxf(bmax, float(P["brake"]) * 0.35)
		fl -= clampf(vwf * m_share / dt, -bmax, bmax)
		fl -= clampf(vwf * 2.0, -1.0, 1.0) * 0.015 * fz   # rolling resistance
		var slip := atan2(vws, maxf(absf(vwf), 3.0))
		var flat := -c_alpha * slip
		var lat_cap := absf(vws) * m_share / dt
		flat = clampf(flat, -lat_cap, lat_cap)
		var lim := grip * fz
		var tot := sqrt(fl * fl + flat * flat)
		if tot > lim and tot > 0.0:
			fl *= lim / tot
			flat *= lim / tot
		apply_force(n * fz, r)
		apply_force(wf * fl + ws * flat, r + up * 0.25)
	apply_central_force(-v * v.length() * float(P["drag"]))
