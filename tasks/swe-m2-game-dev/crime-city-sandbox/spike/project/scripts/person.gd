class_name Person
extends CharacterBody3D
## A person (player or NPC). Logic runs in _physics_process only. The visual is a humanoid
## Skeleton3D (primitive rig or the imported base body) facing the body's -Z.

## Player gait speeds (proposed GDD bands: walk 1.3-1.8, run 3.5-5, sprint 6-7.5 m/s).
## --speeds=native runs the player at the clips' own ground speeds instead (spike measurement).
static var WALK := 1.55
static var RUN := 4.2
static var SPRINT := 6.8

var archetype := "civilian"
var faction := "civilian"
var lead := ""
var behaviour := "wander"      # wander | idle | player
var is_player := false
var visual: Node3D
var anim: AnimationPlayer
var skel: Skeleton3D
var vehicle = null             # car node while seated
var seat := -1
var walk_speed := 1.5
var ring := {}                 # sidewalk dictionary for wander
var ring_s := 0.0
var ring_dir := 1.0
var ring_lat := 0.0
var face_point := Vector3.INF
var desired := Vector3.ZERO
var cur_clip := ""
var cam_yaw := 0.0
var health := 100.0
var yaw := 0.0
var clip_names := {}           # our clip -> library clip
var clip_speeds := {}          # our clip -> natural ground speed (m/s)
var _prev_pos := Vector3.ZERO


func setup(p_archetype: String, p_faction: String, palette: Dictionary, art: String = "primitive") -> void:
	archetype = p_archetype
	faction = p_faction
	var cs := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.3
	cap.height = 1.75
	cs.shape = cap
	cs.position = Vector3(0, 0.875, 0)
	add_child(cs)
	collision_layer = 4
	collision_mask = 1 | 2 | 4 | 16
	floor_max_angle = deg_to_rad(65.0)
	floor_snap_length = 0.35
	if art == "ubc" and RealArt.available():
		visual = RealArt.build_visual(palette)
		clip_names = RealArt.CLIP_NAMES
		clip_speeds = RealArt.clip_speeds()
	else:
		visual = Humanoid.build_visual(palette)
		for c in ["idle", "walk", "run", "sprint", "sit"]:
			clip_names[c] = c
		for c2 in Humanoid.CLIPS:
			clip_speeds[c2] = float(Humanoid.CLIPS[c2]["v"])
	if Game.args.get("speeds", "") == "native" and not clip_speeds.is_empty():
		WALK = clip_speeds.get("walk", WALK)
		RUN = clip_speeds.get("run", RUN)
		SPRINT = clip_speeds.get("sprint", SPRINT)
	visual.rotation.y = PI
	add_child(visual)
	skel = visual.find_children("*", "Skeleton3D", true, false)[0]
	anim = visual.get_node("Anim")
	_play("idle", 1.0)


func set_yaw(y: float) -> void:
	yaw = y
	rotation = Vector3(0, yaw, 0)


func forward() -> Vector3:
	return Vector3(-sin(yaw), 0.0, -cos(yaw))


static func yaw_of(dir: Vector3) -> float:
	return atan2(-dir.x, -dir.z)


func enter_vehicle(car, seat_index: int) -> void:
	vehicle = car
	seat = seat_index
	car.occupants[seat_index] = self
	collision_layer = 0
	collision_mask = 0
	velocity = Vector3.ZERO
	global_transform = car.seat_xform(seat_index)


func exit_vehicle() -> void:
	if vehicle == null:
		return
	var car = vehicle
	car.occupants.erase(seat)
	if seat == 0:
		car.driver_kind = "none"
	var side: Vector3 = car.left_dir() * (1.6 if seat % 2 == 0 else -1.6)
	vehicle = null
	seat = -1
	collision_layer = 4
	collision_mask = 1 | 2 | 4 | 16
	global_position = car.global_position + side + Vector3(0, 0.2, 0)
	set_yaw(yaw_of(car.fwd()))


func _physics_process(dt: float) -> void:
	if vehicle != null:
		if not is_instance_valid(vehicle):
			vehicle = null
			collision_layer = 4
			collision_mask = 1 | 2 | 4 | 16
		else:
			global_transform = vehicle.seat_xform(seat)
			yaw = global_transform.basis.get_euler().y
			_play("sit", 1.0)
			return
	match behaviour:
		"player":
			_player_input(dt)
		"wander":
			_wander()
		"remote":
			pass
		_:
			desired = Vector3.ZERO
	var hv := Vector3(velocity.x, 0.0, velocity.z)
	hv = hv.move_toward(desired, (12.0 if is_player else 6.0) * dt)
	velocity.x = hv.x
	velocity.z = hv.z
	if is_on_floor():
		velocity.y = 0.0
	else:
		velocity.y -= 9.8 * dt
	_prev_pos = global_position
	move_and_slide()
	var moved := global_position - _prev_pos
	var sp := Vector2(moved.x, moved.z).length() / dt
	if desired.length() > 0.1:
		set_yaw(lerp_angle(yaw, yaw_of(desired), minf(1.0, 10.0 * dt)))
	elif face_point != Vector3.INF:
		var fd := face_point - global_position
		if Vector2(fd.x, fd.z).length() > 0.1:
			set_yaw(lerp_angle(yaw, yaw_of(fd), minf(1.0, 6.0 * dt)))
	_update_anim(sp)


func _player_input(dt: float) -> void:
	var look := Input.get_action_strength("look_left") - Input.get_action_strength("look_right")
	cam_yaw = wrapf(cam_yaw + look * 2.0 * dt, -PI, PI)
	var mx := Input.get_action_strength("move_right") - Input.get_action_strength("move_left")
	var my := Input.get_action_strength("move_forward") - Input.get_action_strength("move_back")
	var m := minf(Vector2(mx, my).length(), 1.0)
	if m < 0.05:
		desired = Vector3.ZERO
		return
	var f := Vector3(-sin(cam_yaw), 0.0, -cos(cam_yaw))
	var r := Vector3(cos(cam_yaw), 0.0, -sin(cam_yaw))
	var dir := (f * my + r * mx).normalized()
	var speed := WALK if m <= 0.55 else RUN
	if m > 0.55 and Input.is_action_pressed("sprint"):
		speed = SPRINT
	desired = dir * speed


func _wander() -> void:
	if ring.is_empty():
		desired = Vector3.ZERO
		return
	var here: Dictionary = Game.plan.sidewalk_point(ring, ring_s)
	var t: Vector3 = here["fwd"] * ring_dir
	var to_here := Vector3(global_position.x - here["pos"].x, 0.0, global_position.z - here["pos"].z)
	ring_s += ring_dir * maxf(0.0, to_here.dot(t) + 0.0)
	var ahead: Dictionary = Game.plan.sidewalk_point(ring, ring_s + ring_dir * 2.5)
	var ta: Vector3 = ahead["fwd"] * ring_dir
	var lat := Vector3(-ta.z, 0.0, ta.x) * ring_lat
	var target: Vector3 = ahead["pos"] + lat
	var d := Vector3(target.x - global_position.x, 0.0, target.z - global_position.z)
	if d.length() < 0.05:
		desired = Vector3.ZERO
	else:
		desired = d.normalized() * walk_speed


func _update_anim(sp: float) -> void:
	var clip := cur_clip
	if cur_clip == "" or cur_clip == "sit":
		clip = "idle"
	match clip:
		"idle":
			if sp > 0.35:
				clip = "walk"
		"walk":
			if sp < 0.2:
				clip = "idle"
			elif sp > 3.0:
				clip = "run"
		"run":
			if sp < 2.6:
				clip = "walk"
			elif sp > 5.6:
				clip = "sprint"
		"sprint":
			if sp < 5.2:
				clip = "run"
	var vn: float = clip_speeds.get(clip, 0.0)
	_play(clip, clampf(sp / vn, 0.4, 1.8) if vn > 0.0 else 1.0)


func _play(clip: String, scale: float) -> void:
	if clip != cur_clip:
		anim.play(clip_names.get(clip, clip), 0.15)
		cur_clip = clip
	anim.speed_scale = scale
