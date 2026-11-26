extends Node3D
## Tiny Town: the smallest game that follows the automation contract closely enough for
## the QA kit to check itself. A flat ground, a rigged player that walks with the move
## actions and waves its right arm one degree per tick, people and physics crates placed
## from the variation, a clock, money, and atomic saves in --save-dir.
## An optional res://hostile.gd (absent here) is added as a child and given hooks; the
## kit's checks use it to build broken copies of this project.

const WALK_SPEED := 3.0
const NPC_SPEED := 1.2
const ARCHETYPES := ["office_worker", "shopper", "tourist", "student"]
const BONES := [
	["Hips", "", Vector3(0, 1.0, 0)],
	["Spine", "Hips", Vector3(0, 0.2, 0)],
	["Chest", "Spine", Vector3(0, 0.2, 0)],
	["Neck", "Chest", Vector3(0, 0.15, 0)],
	["Head", "Neck", Vector3(0, 0.1, 0)],
	["RightUpperArm", "Chest", Vector3(-0.2, 0, 0)],
	["RightLowerArm", "RightUpperArm", Vector3(-0.3, 0, 0)],
	["RightHand", "RightLowerArm", Vector3(-0.25, 0, 0)],
	["LeftUpperArm", "Chest", Vector3(0.2, 0, 0)],
	["LeftLowerArm", "LeftUpperArm", Vector3(0.3, 0, 0)],
	["LeftHand", "LeftLowerArm", Vector3(0.25, 0, 0)],
	["LeftUpperLeg", "Hips", Vector3(0.1, -0.05, 0)],
	["LeftLowerLeg", "LeftUpperLeg", Vector3(0, -0.45, 0)],
	["LeftFoot", "LeftLowerLeg", Vector3(0, -0.45, 0)],
	["LeftToes", "LeftFoot", Vector3(0, -0.05, -0.12)],
	["RightUpperLeg", "Hips", Vector3(-0.1, -0.05, 0)],
	["RightLowerLeg", "RightUpperLeg", Vector3(0, -0.45, 0)],
	["RightFoot", "RightLowerLeg", Vector3(0, -0.45, 0)],
	["RightToes", "RightFoot", Vector3(0, -0.05, -0.12)],
]

var variation := 1
var save_dir := "user://saves"
var role := "solo"
var next_id := 1
var reset_tick := 0
var clock_min := 480
var weather := "clear"
var money := 500
var player: CharacterBody3D = null
var skeleton: Skeleton3D = null
var arm_bone := -1
var arm_deg := 0
var npcs: Array[Node3D] = []
var bodies: Array[RigidBody3D] = []
var camera: Camera3D = null
var hostile: Node = null


func _ready() -> void:
	_read_args()
	DevConsole.world = self
	_build_ground()
	camera = Camera3D.new()
	add_child(camera)
	camera.current = true
	if ResourceLoader.exists("res://hostile.gd"):
		hostile = load("res://hostile.gd").new()
		hostile.set("world", self)
		add_child(hostile)
	reset_world({"variation": variation})
	spawn_player({"at": [0.0, 0.0, 0.0]})


func _read_args() -> void:
	for a in OS.get_cmdline_user_args():
		var value: String = a.substr(a.find("=") + 1)
		if a.begins_with("--variation="):
			variation = int(value)
		elif a.begins_with("--save-dir="):
			save_dir = value
		elif a.begins_with("--role="):
			role = value


func _build_ground() -> void:
	var ground := StaticBody3D.new()
	var shape := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(400, 1, 400)
	shape.shape = box
	ground.add_child(shape)
	ground.position = Vector3(0, -0.5, 0)
	ground.set_meta("surface", "road")
	add_child(ground)


func _register(node: Node3D, kind: String, archetype: String, faction: String) -> void:
	node.add_to_group("entity")
	node.set_meta("entity_id", next_id)
	node.set_meta("kind", kind)
	node.set_meta("archetype", archetype)
	node.set_meta("faction", faction)
	next_id += 1


func _number(v) -> bool:
	return typeof(v) == TYPE_INT or typeof(v) == TYPE_FLOAT


func _slot(args: Dictionary) -> String:
	var s = args.get("slot", null)
	if _number(s) and int(s) >= 1 and int(s) <= 3 and float(s) == float(int(s)):
		return str(int(s))
	return ""


# ------------------------------------------------------------------ commands
func reset_world(args: Dictionary) -> Dictionary:
	var v = args.get("variation", variation)
	if not _number(v):
		return {"ok": false, "error": "variation must be a number"}
	variation = int(v)
	for n in npcs:
		remove_child(n)
		n.queue_free()
	npcs.clear()
	for b in bodies:
		remove_child(b)
		b.queue_free()
	bodies.clear()
	var rng := RandomNumberGenerator.new()
	rng.seed = variation * 7919 + 17
	for i in range(6):
		var npc := CharacterBody3D.new()
		npc.collision_layer = 4
		npc.collision_mask = 0
		var shape := CollisionShape3D.new()
		shape.shape = CapsuleShape3D.new()
		shape.position = Vector3(0, 0.9, 0)
		npc.add_child(shape)
		npc.position = Vector3(rng.randf_range(-20, 20), 0, rng.randf_range(-20, 20))
		var ang := rng.randf_range(0, TAU)
		npc.set_meta("dir", Vector3(cos(ang), 0, sin(ang)))
		_register(npc, "npc", ARCHETYPES[rng.randi_range(0, ARCHETYPES.size() - 1)], "civilian")
		npc.set_meta("weapon", "none")
		npc.set_meta("hostile", false)
		add_child(npc)
		npcs.append(npc)
	for i in range(2):
		var crate := RigidBody3D.new()
		crate.collision_layer = 16
		crate.collision_mask = 1 | 16
		crate.mass = 10.0
		var cs := CollisionShape3D.new()
		var cb := BoxShape3D.new()
		cb.size = Vector3(0.5, 0.5, 0.5)
		cs.shape = cb
		crate.add_child(cs)
		crate.position = Vector3(rng.randf_range(-5, 5), 3.0 + i, rng.randf_range(-5, 5))
		crate.rotation = Vector3(rng.randf_range(0, 1), rng.randf_range(0, 1), 0)
		_register(crate, "prop", "crate", "none")
		add_child(crate)
		bodies.append(crate)
	reset_tick = Engine.get_physics_frames()
	clock_min = 480
	weather = "clear"
	if hostile and hostile.has_method("on_reset"):
		hostile.on_reset()
	return {"ok": true}


func spawn_player(args: Dictionary) -> Dictionary:
	var at = args.get("at", [0.0, 0.0, 0.0])
	if not (at is Array) or at.size() != 3 or not (_number(at[0]) and _number(at[1]) and _number(at[2])):
		return {"ok": false, "error": "at must be [x, y, z]"}
	if player == null:
		player = _make_player()
		add_child(player)
	player.global_position = Vector3(float(at[0]), float(at[1]), float(at[2]))
	DevConsole.emit_event("teleport", {"entity": player.get_meta("entity_id"), "reason": "setup"})
	return {"ok": true, "id": player.get_meta("entity_id")}


func give(args: Dictionary) -> Dictionary:
	var m = args.get("money", null)
	if not _number(m):
		return {"ok": false, "error": "only money can be given here"}
	money += int(m)
	DevConsole.emit_event("money_changed", {"amount": int(m), "reason": "setup", "balance": money})
	return {"ok": true}


func set_time(args: Dictionary) -> Dictionary:
	var hhmm = args.get("hhmm", "")
	if typeof(hhmm) != TYPE_STRING or hhmm.length() != 5 or hhmm[2] != ":":
		return {"ok": false, "error": "hhmm must look like 08:30"}
	var h := int(hhmm.substr(0, 2))
	var m := int(hhmm.substr(3, 2))
	if h < 0 or h > 23 or m < 0 or m > 59:
		return {"ok": false, "error": "hhmm out of range"}
	clock_min = h * 60 + m
	return {"ok": true}


func set_weather(args: Dictionary) -> Dictionary:
	var k = args.get("kind", "")
	if not (k in ["clear", "overcast", "rain", "fog"]):
		return {"ok": false, "error": "unknown weather"}
	weather = k
	return {"ok": true}


func save_slot(args: Dictionary) -> Dictionary:
	var slot := _slot(args)
	if slot == "":
		return {"ok": false, "error": "slot must be 1, 2 or 3"}
	DirAccess.make_dir_recursive_absolute(save_dir)
	var p := player.global_position if player else Vector3.ZERO
	var data := {"version": 1, "money": money, "clock_min": clock_min, "weather": weather,
		"variation": variation, "position": [p.x, p.y, p.z]}
	var path := save_dir.path_join("slot_%s.json" % slot)
	var tmp := path + ".tmp"
	var f := FileAccess.open(tmp, FileAccess.WRITE)
	if f == null:
		return {"ok": false, "error": "cannot write the save"}
	f.store_string(JSON.stringify(data))
	f.close()
	if DirAccess.rename_absolute(tmp, path) != OK:
		return {"ok": false, "error": "cannot write the save"}
	DevConsole.emit_event("saved", {"slot": slot})
	return {"ok": true}


func load_slot(args: Dictionary) -> Dictionary:
	var slot := _slot(args)
	if slot == "":
		return {"ok": false, "error": "slot must be 1, 2 or 3"}
	var path := save_dir.path_join("slot_%s.json" % slot)
	if not FileAccess.file_exists(path):
		return {"ok": false, "error": "Slot %s is empty" % slot}
	var data = JSON.parse_string(FileAccess.get_file_as_string(path))
	if not _valid_save(data):
		if hostile and hostile.has_method("on_damaged_save"):
			hostile.on_damaged_save()
		return {"ok": false, "error": "Slot %s is damaged" % slot}
	money = int(data["money"])
	clock_min = int(data["clock_min"])
	weather = str(data["weather"])
	var pos: Array = data["position"]
	if player:
		player.global_position = Vector3(float(pos[0]), float(pos[1]), float(pos[2]))
		DevConsole.emit_event("teleport", {"entity": player.get_meta("entity_id"), "reason": "load"})
	DevConsole.emit_event("money_changed", {"amount": 0, "reason": "load", "balance": money})
	DevConsole.emit_event("loaded", {"slot": slot})
	return {"ok": true}


func _valid_save(data) -> bool:
	if not (data is Dictionary):
		return false
	for k in ["money", "clock_min", "weather", "position"]:
		if not data.has(k):
			return false
	if not _number(data["money"]) or not _number(data["clock_min"]):
		return false
	var pos = data["position"]
	return pos is Array and pos.size() == 3 and _number(pos[0]) and _number(pos[1]) and _number(pos[2])


func state_report() -> Dictionary:
	var p := player.global_position if player else Vector3.ZERO
	return {
		"ok": true,
		"tick": Engine.get_physics_frames() - reset_tick,
		"map": "downtown",
		"clock": "%02d:%02d" % [clock_min / 60, clock_min % 60],
		"weather": weather,
		"variation": variation,
		"player": {
			"id": player.get_meta("entity_id") if player else null,
			"lead": "lead_1", "health": 100, "armour": 0, "money": money, "alert": 0,
			"weapon": "fists", "weapons": ["fists"], "ammo": {"magazine": 0, "reserve": 0},
			"aim": null, "cover": false, "vehicle": null, "seat": null, "limp": false,
			"outfit": "default",
			"outfits": ["default"], "leads_unlocked": ["lead_1"], "position": [p.x, p.y, p.z],
		},
		"missions": {}, "garages": {},
		"ui": {"phone": false, "map": false, "paused": false, "menu": null},
		"network": {"role": role, "peers": 0, "id": 1},
		"arm_deg": arm_deg,
		"key_visible": OS.get_environment("QA_TELEMETRY_KEY") != "",
	}


# ------------------------------------------------------------------ the player
func _make_player() -> CharacterBody3D:
	var body := CharacterBody3D.new()
	body.collision_layer = 4
	body.collision_mask = 0
	var shape := CollisionShape3D.new()
	var cap := CapsuleShape3D.new()
	cap.radius = 0.4
	cap.height = 1.8
	shape.shape = cap
	shape.position = Vector3(0, 0.9, 0)
	body.add_child(shape)
	var model := Node3D.new()
	model.name = "Model"
	body.add_child(model)
	skeleton = Skeleton3D.new()
	skeleton.name = "Skeleton"
	for b in BONES:
		skeleton.add_bone(b[0])
	for i in range(BONES.size()):
		var parent: String = BONES[i][1]
		if parent != "":
			skeleton.set_bone_parent(i, skeleton.find_bone(parent))
		skeleton.set_bone_rest(i, Transform3D(Basis.IDENTITY, BONES[i][2]))
	skeleton.reset_bone_poses()
	model.add_child(skeleton)
	arm_bone = skeleton.find_bone("RightUpperArm")
	skeleton.add_child(_skinned_box(skeleton))
	_register(body, "player", "lead_1", "player")
	body.set_meta("weapon", "none")
	body.set_meta("hostile", false)
	return body


func _skinned_box(sk: Skeleton3D) -> MeshInstance3D:
	var chest := sk.find_bone("Chest")
	var box := BoxMesh.new()
	box.size = Vector3(0.4, 0.5, 0.25)
	var arrays := box.get_mesh_arrays()
	var n: int = arrays[Mesh.ARRAY_VERTEX].size()
	var verts: PackedVector3Array = arrays[Mesh.ARRAY_VERTEX]
	for i in range(n):
		verts[i] += Vector3(0, 1.4, 0)
	arrays[Mesh.ARRAY_VERTEX] = verts
	var bones := PackedInt32Array()
	var weights := PackedFloat32Array()
	for i in range(n):
		for k in range(4):
			bones.append(chest if k == 0 else 0)
			weights.append(1.0 if k == 0 else 0.0)
	arrays[Mesh.ARRAY_BONES] = bones
	arrays[Mesh.ARRAY_WEIGHTS] = weights
	var mesh := ArrayMesh.new()
	mesh.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var skin := Skin.new()
	skin.add_named_bind("Chest", sk.get_bone_global_rest(chest).affine_inverse())
	var mi := MeshInstance3D.new()
	mi.name = "Body"
	mi.mesh = mesh
	mi.skin = skin
	mi.skeleton = NodePath("..")
	return mi


# ------------------------------------------------------------------ the tick
func _physics_process(_delta: float) -> void:
	if (Engine.get_physics_frames() - reset_tick) % 60 == 0:
		clock_min = (clock_min + 1) % 1440
	if player:
		var f := Input.get_action_strength("move_forward") - Input.get_action_strength("move_back")
		var r := Input.get_action_strength("move_right") - Input.get_action_strength("move_left")
		player.velocity = Vector3(r, 0, -f) * WALK_SPEED
		player.move_and_slide()
		arm_deg += 1
		skeleton.set_bone_pose_rotation(arm_bone, Quaternion(Vector3(0, 0, 1), deg_to_rad(arm_deg)))
		camera.global_position = player.global_position + Vector3(0, 3, 5)
		camera.look_at(player.global_position + Vector3(0, 1, 0))
	for n in npcs:
		var d: Vector3 = n.get_meta("dir")
		var next: Vector3 = n.position + d * NPC_SPEED / 60.0
		if absf(next.x) > 30 or absf(next.z) > 30:
			d = -d
			n.set_meta("dir", d)
			next = n.position + d * NPC_SPEED / 60.0
		n.position = next
