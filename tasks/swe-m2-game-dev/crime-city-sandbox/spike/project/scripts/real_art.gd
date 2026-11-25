class_name RealArt
extends RefCounted
## People made from the imported CC0 library: Quaternius Universal Base Characters (bones
## renamed to Godot's humanoid profile by a BoneMap at import, skeleton made unique as
## %GeneralSkeleton) animated by the Universal Animation Library (imported as an
## AnimationLibrary with the same BoneMap, so its tracks target %GeneralSkeleton:<ProfileBone>).
## Clip ground speeds come from the root-motion copy of the library.

const BODY_PATHS := ["res://assets/vendor/ubc/Superhero_Male_FullBody.gltf",
	"res://assets/vendor/ubc/Superhero_Female_FullBody.gltf"]
const HAIR_PATH := "res://assets/vendor/ubc_hair/Hair_SimpleParted.gltf"
const LIB_PATH := "res://assets/vendor/ual/UAL1_Standard.glb"
const RM_LIB_PATH := "res://assets/vendor/ual/UAL1_Standard_RM.glb"
const CLIP_NAMES := {"idle": "Idle", "walk": "Walk", "run": "Jog_Fwd", "sprint": "Sprint", "sit": "Driving"}

static var _bodies: Array = []
static var _hair: PackedScene
static var _lib: AnimationLibrary
static var _speeds := {}
static var motion_scale := 1.0
static var _n := 0


static func available() -> bool:
	return ResourceLoader.exists(BODY_PATHS[0]) and ResourceLoader.exists(LIB_PATH)


static func _init_once() -> void:
	if _lib != null:
		return
	for p in BODY_PATHS:
		_bodies.append(load(p))
	_lib = load(LIB_PATH)
	_hair = load(HAIR_PATH) if ResourceLoader.exists(HAIR_PATH) else null
	var tmp: Node = _bodies[0].instantiate()
	var sk: Skeleton3D = tmp.find_children("*", "Skeleton3D", true, false)[0]
	motion_scale = sk.motion_scale
	tmp.free()
	var rm: AnimationLibrary = load(RM_LIB_PATH) if ResourceLoader.exists(RM_LIB_PATH) else null
	for k in CLIP_NAMES:
		var v := 0.0
		if rm != null and rm.has_animation(CLIP_NAMES[k]):
			var a := rm.get_animation(CLIP_NAMES[k])
			var t := a.find_track(NodePath("%GeneralSkeleton:Root"), Animation.TYPE_POSITION_3D)
			if t >= 0:
				var p0 := a.position_track_interpolate(t, 0.0)
				var p1 := a.position_track_interpolate(t, a.length)
				v = Vector2(p1.x - p0.x, p1.z - p0.z).length() / a.length * motion_scale
		_speeds[k] = v


static func clip_speeds() -> Dictionary:
	_init_once()
	var out := {}
	for k in _speeds:
		if _speeds[k] > 0.05:
			out[k] = _speeds[k]
	return out


static func build_visual(_palette: Dictionary) -> Node3D:
	_init_once()
	var body: Node3D = _bodies[_n % _bodies.size()].instantiate()
	_n += 1
	body.name = "Visual"
	var sk: Skeleton3D = body.find_children("*", "Skeleton3D", true, false)[0]
	sk.modifier_callback_mode_process = Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	if _hair != null:
		var h := _hair.instantiate()
		for mi in h.find_children("*", "MeshInstance3D", true, false):
			mi.get_parent().remove_child(mi)
			mi.owner = null
			sk.add_child(mi)
			mi.skeleton = NodePath("..")
		h.free()
	var ap := AnimationPlayer.new()
	ap.name = "Anim"
	body.add_child(ap)
	ap.root_node = NodePath("..")
	ap.callback_mode_process = AnimationMixer.ANIMATION_CALLBACK_MODE_PROCESS_PHYSICS
	ap.add_animation_library("", _lib)
	return body
