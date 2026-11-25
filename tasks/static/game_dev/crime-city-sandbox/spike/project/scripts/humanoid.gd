class_name Humanoid
extends RefCounted
## Primitive humanoid for the spike: a Skeleton3D with Godot's humanoid-profile bones, built in
## code from SkeletonProfileHumanoid's reference pose, a skinned box mesh bound to it, and
## procedural clips (idle, walk, run, sprint, sit). Stance feet stay planted when a clip plays
## at speed_scale = ground speed / clip speed.

const CLIPS := {
	"walk": {"v": 1.5, "T": 1.05, "duty": 0.62, "lift": 0.10, "lean": 0.03, "arm": 0.45, "elbow": 0.25},
	"run": {"v": 4.2, "T": 0.66, "duty": 0.36, "lift": 0.18, "lean": 0.12, "arm": 0.8, "elbow": 1.2},
	"sprint": {"v": 6.6, "T": 0.60, "duty": 0.30, "lift": 0.22, "lean": 0.2, "arm": 1.0, "elbow": 1.4},
}
const KEYS := 24
const SIDES := ["Left", "Right"]
## The profile's reference pose is about 1.45 m tall; scale it to an adult (about 1.75 m).
const SCALE := 1.22

static var _inited := false
static var names := PackedStringArray()
static var parents := PackedInt32Array()
static var rest_local: Array = []
static var rest_global: Array = []
static var _meshes := {}
static var _skin: Skin
static var _lib: AnimationLibrary
static var l1 := 0.0
static var l2 := 0.0
static var height := 0.0
static var _arm_lower := {}


static func idx(n: String) -> int:
	return names.find(n)


static func init() -> void:
	if _inited:
		return
	_inited = true
	var prof := SkeletonProfileHumanoid.new()
	var n := prof.bone_size
	for i in range(n):
		names.append(String(prof.get_bone_name(i)))
	for i in range(n):
		var pn := String(prof.get_bone_parent(i))
		parents.append(names.find(pn) if pn != "" else -1)
		var rp: Transform3D = prof.get_reference_pose(i)
		rest_local.append(Transform3D(rp.basis, rp.origin * SCALE))
		rest_global.append(Transform3D.IDENTITY)
	var done := {}
	for i in range(n):
		_global_of(i, done)
	l1 = rest_global[idx("LeftUpperLeg")].origin.distance_to(rest_global[idx("LeftLowerLeg")].origin)
	l2 = rest_global[idx("LeftLowerLeg")].origin.distance_to(rest_global[idx("LeftFoot")].origin)
	height = rest_global[idx("Head")].origin.y + 0.24
	for side in SIDES:
		var ua: Vector3 = rest_global[idx(side + "UpperArm")].origin
		var la: Vector3 = rest_global[idx(side + "LowerArm")].origin
		var rest_dir := (la - ua).normalized()
		var sx := signf(rest_dir.x)
		var target := Vector3(0.28 * sx, -0.96, 0.0).normalized()
		_arm_lower[side] = Basis(Quaternion(rest_dir, target))
	_skin = Skin.new()
	for i in range(n):
		_skin.add_named_bind(names[i], rest_global[i].affine_inverse())
	_lib = AnimationLibrary.new()
	_lib.add_animation("idle", _make_clip("idle"))
	for c in CLIPS:
		_lib.add_animation(c, _make_clip(c))
	_lib.add_animation("sit", _make_clip("sit"))


static func _global_of(i: int, done: Dictionary) -> Transform3D:
	if done.has(i):
		return rest_global[i]
	var p := parents[i]
	var g: Transform3D = rest_local[i]
	if p >= 0:
		g = _global_of(p, done) * rest_local[i]
	rest_global[i] = g
	done[i] = true
	return g


## The visual node: Visual/Skeleton3D/Body (skinned) and Visual/Anim (AnimationPlayer).
static func build_visual(palette: Dictionary) -> Node3D:
	init()
	var vis := Node3D.new()
	vis.name = "Visual"
	var sk := Skeleton3D.new()
	sk.name = "Skeleton3D"
	for i in range(names.size()):
		sk.add_bone(names[i])
	for i in range(names.size()):
		if parents[i] >= 0:
			sk.set_bone_parent(i, parents[i])
		sk.set_bone_rest(i, rest_local[i])
	sk.reset_bone_poses()
	sk.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	vis.add_child(sk)
	var mi := MeshInstance3D.new()
	mi.name = "Body"
	mi.mesh = _mesh_for(palette)
	mi.skin = _skin
	sk.add_child(mi)
	mi.skeleton = NodePath("..")
	var ap := AnimationPlayer.new()
	ap.name = "Anim"
	vis.add_child(ap)
	ap.root_node = NodePath("..")
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	ap.add_animation_library("", _lib)
	return vis


# ---------------------------------------------------------------- mesh

static func _mesh_for(palette: Dictionary) -> ArrayMesh:
	var key := str(palette)
	if _meshes.has(key):
		return _meshes[key]
	var verts := PackedVector3Array()
	var norms := PackedVector3Array()
	var cols := PackedColorArray()
	var bones := PackedInt32Array()
	var weights := PackedFloat32Array()
	var inds := PackedInt32Array()
	var skin_c: Color = palette.get("skin", Color(0.8, 0.65, 0.5))
	var shirt: Color = palette.get("shirt", Color(0.2, 0.3, 0.7))
	var pants: Color = palette.get("pants", Color(0.15, 0.15, 0.2))
	var shoes: Color = palette.get("shoes", Color(0.1, 0.08, 0.06))
	var G := func(n: String) -> Vector3: return rest_global[idx(n)].origin
	var parts: Array = [
		["Hips", G.call("Hips") - Vector3(0, 0.1, 0), G.call("Spine"), 0.32, 0.2, pants],
		["Spine", G.call("Spine"), G.call("Chest"), 0.3, 0.19, shirt],
		["Chest", G.call("Chest"), G.call("UpperChest"), 0.33, 0.2, shirt],
		["UpperChest", G.call("UpperChest"), G.call("Neck"), 0.36, 0.21, shirt],
		["Neck", G.call("Neck"), G.call("Head"), 0.1, 0.1, skin_c],
		["Head", G.call("Head"), G.call("Head") + Vector3(0, 0.24, 0), 0.19, 0.22, skin_c],
	]
	for side in SIDES:
		parts.append([side + "Shoulder", G.call(side + "Shoulder"), G.call(side + "UpperArm"), 0.1, 0.1, shirt])
		parts.append([side + "UpperArm", G.call(side + "UpperArm"), G.call(side + "LowerArm"), 0.1, 0.1, shirt])
		parts.append([side + "LowerArm", G.call(side + "LowerArm"), G.call(side + "Hand"), 0.08, 0.08, skin_c])
		var hand: Vector3 = G.call(side + "Hand")
		parts.append([side + "Hand", hand, hand + (G.call(side + "MiddleProximal") - hand) * 1.8, 0.09, 0.04, skin_c])
		parts.append([side + "UpperLeg", G.call(side + "UpperLeg"), G.call(side + "LowerLeg"), 0.15, 0.15, pants])
		parts.append([side + "LowerLeg", G.call(side + "LowerLeg"), G.call(side + "Foot"), 0.11, 0.11, pants])
		var foot: Vector3 = G.call(side + "Foot")
		var toes: Vector3 = G.call(side + "Toes")
		parts.append([side + "Foot", Vector3(foot.x, foot.y + 0.03, foot.z - 0.05), Vector3(toes.x, 0.0, toes.z), 0.1, foot.y + 0.03, shoes])
		parts.append([side + "Toes", Vector3(toes.x, 0.03, toes.z), Vector3(toes.x, 0.03, toes.z + 0.06), 0.09, 0.05, shoes])
	for part in parts:
		_add_box(part, verts, norms, cols, bones, weights, inds)
	var arrays := []
	arrays.resize(Mesh.ARRAY_MAX)
	arrays[Mesh.ARRAY_VERTEX] = verts
	arrays[Mesh.ARRAY_NORMAL] = norms
	arrays[Mesh.ARRAY_COLOR] = cols
	arrays[Mesh.ARRAY_BONES] = bones
	arrays[Mesh.ARRAY_WEIGHTS] = weights
	arrays[Mesh.ARRAY_INDEX] = inds
	var m := ArrayMesh.new()
	m.add_surface_from_arrays(Mesh.PRIMITIVE_TRIANGLES, arrays)
	var mat := StandardMaterial3D.new()
	mat.vertex_color_use_as_albedo = true
	m.surface_set_material(0, mat)
	_meshes[key] = m
	return m


static func _add_box(part: Array, verts: PackedVector3Array, norms: PackedVector3Array,
		cols: PackedColorArray, bones: PackedInt32Array, weights: PackedFloat32Array,
		inds: PackedInt32Array) -> void:
	var bi := idx(part[0])
	var a: Vector3 = part[1]
	var b: Vector3 = part[2]
	var u := (b - a)
	var hu := u.length() * 0.5 + 0.01
	u = u.normalized()
	var ref := Vector3.RIGHT if absf(u.y) > 0.7 else Vector3.UP
	var w := (ref - u * ref.dot(u)).normalized()
	var d := u.cross(w)
	var hw: float = float(part[3]) * 0.5
	var hd: float = float(part[4]) * 0.5
	var c := (a + b) * 0.5
	var faces := [[u, w, d, hu, hw, hd], [-u, d, w, hu, hd, hw], [w, d, u, hw, hd, hu],
		[-w, u, d, hw, hu, hd], [d, u, w, hd, hu, hw], [-d, w, u, hd, hw, hu]]
	for f in faces:
		var n: Vector3 = f[0]
		var ax: Vector3 = f[1]
		var bx: Vector3 = f[2]
		var hn: float = f[3]
		var ha: float = f[4]
		var hb: float = f[5]
		var base := verts.size()
		var fc := c + n * hn
		for corner in [Vector2(-1, -1), Vector2(1, -1), Vector2(1, 1), Vector2(-1, 1)]:
			verts.append(fc + ax * (corner.x * ha) + bx * (corner.y * hb))
			norms.append(n)
			cols.append(part[5])
			bones.append_array([bi, 0, 0, 0])
			weights.append_array([1.0, 0.0, 0.0, 0.0])
		inds.append_array([base, base + 2, base + 1, base, base + 3, base + 2])


# ---------------------------------------------------------------- clips

static func _ik(zt: float, yt: float) -> Vector2:
	## Two-link leg in the sagittal plane. Returns (thigh, shin) forward angles from vertical.
	var d := clampf(sqrt(zt * zt + yt * yt), 0.05, l1 + l2 - 1e-4)
	var phi := atan2(zt, -yt)
	var a := acos(clampf((l1 * l1 + d * d - l2 * l2) / (2.0 * l1 * d), -1.0, 1.0))
	var b := acos(clampf((l2 * l2 + d * d - l1 * l1) / (2.0 * l2 * d), -1.0, 1.0))
	return Vector2(phi + a, phi - b)


static func _pose_at(clip: String, u: float) -> Dictionary:
	## Returns {"D": {bone: Basis (skeleton-space delta)}, "drop": hip drop in metres}.
	var D := {}
	var L := l1 + l2
	var leff := 0.995 * L
	if clip == "idle" or clip == "sit":
		for side in SIDES:
			var low: Basis = _arm_lower[side]
			if clip == "sit":
				D[side + "UpperLeg"] = Basis(Vector3.RIGHT, -1.45)
				D[side + "LowerLeg"] = Basis(Vector3.RIGHT, -0.12)
				D[side + "Foot"] = Basis.IDENTITY
				D[side + "UpperArm"] = Basis(Vector3.RIGHT, -0.9) * low
				D[side + "LowerArm"] = Basis(Vector3.RIGHT, -1.3) * low
			else:
				D[side + "UpperArm"] = low
				D[side + "LowerArm"] = Basis(Vector3.RIGHT, -0.1) * low
		D["Spine"] = Basis(Vector3.RIGHT, 0.02 * sin(TAU * u))
		return {"D": D, "drop": 0.45 if clip == "sit" else L - leff}
	var c: Dictionary = CLIPS[clip]
	var duty: float = c["duty"]
	var stride: float = float(c["v"]) * duty * float(c["T"])
	var feet := {}
	var drop := L - leff
	for si in range(2):
		var side: String = SIDES[si]
		var p := fposmod(u + 0.5 * si, 1.0)
		var z := 0.0
		var lift := 0.0
		var stance := p < duty
		if stance:
			z = stride * 0.5 - (p / duty) * stride
		else:
			# Hermite swing whose end velocities match the stance (zero speed over the ground),
			# so the foot neither skids at lift-off nor at touch-down
			var q := (p - duty) / (1.0 - duty)
			var m := -float(c["v"]) * (1.0 - duty) * float(c["T"])
			var q2 := q * q
			var q3 := q2 * q
			z = (2.0 * q3 - 3.0 * q2 + 1.0) * (-stride * 0.5) + (q3 - 2.0 * q2 + q) * m \
				+ (-2.0 * q3 + 3.0 * q2) * (stride * 0.5) + (q3 - q2) * m
			lift = float(c["lift"]) * sin(PI * q)
		feet[side] = [z, lift, stance]
		if stance:
			drop = maxf(drop, L - sqrt(maxf(leff * leff - z * z, 0.0)))
	var swing_l := 0.0
	var swing_r := 0.0
	for side in SIDES:
		var f: Array = feet[side]
		var ang := _ik(f[0], -(L - drop) + f[1])
		D[side + "UpperLeg"] = Basis(Vector3.RIGHT, -ang.x)
		D[side + "LowerLeg"] = Basis(Vector3.RIGHT, -ang.y)
		D[side + "Foot"] = Basis.IDENTITY
		if side == "Left":
			swing_l = ang.x
		else:
			swing_r = ang.x
	for side in SIDES:
		var low2: Basis = _arm_lower[side]
		var opp := swing_r if side == "Left" else swing_l
		var arm := float(c["arm"]) * opp
		D[side + "UpperArm"] = Basis(Vector3.RIGHT, -arm) * low2
		D[side + "LowerArm"] = Basis(Vector3.RIGHT, -(arm + float(c["elbow"]))) * low2
	D["Spine"] = Basis(Vector3.RIGHT, float(c["lean"]))
	return {"D": D, "drop": drop}


static func _local_rotations(D: Dictionary) -> Array:
	## Converts skeleton-space deltas into local pose rotations for every bone.
	var n := names.size()
	var dg: Array = []
	dg.resize(n)
	var out: Array = []
	out.resize(n)
	for i in range(n):
		var p := parents[i]
		var di: Basis = D.get(names[i], dg[p] if p >= 0 else Basis.IDENTITY)
		dg[i] = di
		var gi: Basis = di * rest_global[i].basis
		var gp: Basis = Basis.IDENTITY
		if p >= 0:
			gp = dg[p] * rest_global[p].basis
		out[i] = Quaternion((gp.inverse() * gi).orthonormalized())
	return out


static func _make_clip(clip: String) -> Animation:
	var T := 2.4
	if CLIPS.has(clip):
		T = float(CLIPS[clip]["T"])
	elif clip == "sit":
		T = 1.0
	var a := Animation.new()
	a.length = T
	a.loop_mode = Animation.LOOP_LINEAR
	var n := names.size()
	var keys: Array = []
	var drops: Array = []
	for k in range(KEYS + 1):
		var pose := _pose_at(clip, float(k) / KEYS)
		keys.append(_local_rotations(pose["D"]))
		drops.append(pose["drop"])
	for i in range(n):
		var tr := a.add_track(Animation.TYPE_ROTATION_3D)
		a.track_set_path(tr, NodePath("Skeleton3D:" + names[i]))
		var constant := true
		for k in range(1, KEYS + 1):
			var q0: Quaternion = keys[0][i]
			var qk: Quaternion = keys[k][i]
			if not q0.is_equal_approx(qk):
				constant = false
				break
		if constant:
			a.rotation_track_insert_key(tr, 0.0, keys[0][i])
			a.rotation_track_insert_key(tr, T, keys[0][i])
		else:
			for k in range(KEYS + 1):
				a.rotation_track_insert_key(tr, T * k / KEYS, keys[k][i])
	var hips := idx("Hips")
	var ptr := a.add_track(Animation.TYPE_POSITION_3D)
	a.track_set_path(ptr, NodePath("Skeleton3D:Hips"))
	var base: Vector3 = rest_local[hips].origin
	for k in range(KEYS + 1):
		a.position_track_insert_key(ptr, T * k / KEYS, base - Vector3(0, drops[k], 0))
	return a
