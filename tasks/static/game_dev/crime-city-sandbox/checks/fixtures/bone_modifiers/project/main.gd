extends Node3D
## Two rigged people, entity 1 (kind "player", at (3, 0, -2), turned 90 degrees about y) and
## entity 2 (kind "npc", at (-4, 0, 5)). Each skeleton has a SkeletonModifier3D that turns
## the left upper arm about +z to a new angle at every skeleton update, step_deg further
## each time, and moves the head along z (the player's by 0.3 m, the other's by -0.25 m).
## The player's modifier runs in the idle step (the engine's default), the other's in the
## physics step. The game itself turns the player's right upper arm about +z, one degree per
## tick. The engine applies a modifier's pose only while it updates the skeleton and
## restores the unmodified pose afterwards; the state report gives the angles used last, so
## a bone read can be compared with where the game put each bone.

const BONES := [
	["Hips", "", Vector3(0, 1.0, 0)],
	["Spine", "Hips", Vector3(0, 0.2, 0)],
	["Chest", "Spine", Vector3(0, 0.2, 0)],
	["Neck", "Chest", Vector3(0, 0.15, 0)],
	["Head", "Neck", Vector3(0, 0.1, 0)],
	["LeftUpperArm", "Chest", Vector3(0.2, 0, 0)],
	["LeftLowerArm", "LeftUpperArm", Vector3(0.3, 0, 0)],
	["LeftHand", "LeftLowerArm", Vector3(0.25, 0, 0)],
	["RightUpperArm", "Chest", Vector3(-0.2, 0, 0)],
	["RightLowerArm", "RightUpperArm", Vector3(-0.3, 0, 0)],
	["RightHand", "RightLowerArm", Vector3(-0.25, 0, 0)],
	["LeftUpperLeg", "Hips", Vector3(0.1, -0.05, 0)],
	["LeftLowerLeg", "LeftUpperLeg", Vector3(0, -0.45, 0)],
	["LeftFoot", "LeftLowerLeg", Vector3(0, -0.45, 0)],
	["LeftToes", "LeftFoot", Vector3(0, -0.05, -0.12)],
]


class Raise extends SkeletonModifier3D:
	## Turns the left upper arm to a new angle at every update and offsets the head;
	## deg is the angle used last.
	var deg := 0.0
	var step_deg := 0.0
	var head_offset := Vector3.ZERO

	func _process_modification_with_delta(_delta: float) -> void:
		var sk := get_skeleton()
		deg += step_deg
		var arm := sk.find_bone("LeftUpperArm")
		sk.set_bone_pose_rotation(arm, Quaternion(Vector3(0, 0, 1), deg_to_rad(deg)))
		var head := sk.find_bone("Head")
		sk.set_bone_pose_position(head, sk.get_bone_rest(head).origin + head_offset)


var next_id := 1
var arm_deg := 0
var player_skeleton: Skeleton3D = null
var player_mod: Raise = null
var npc_mod: Raise = null


func _ready() -> void:
	DevConsole.world = self
	var idle := Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_IDLE
	var physics := Skeleton3D.MODIFIER_CALLBACK_MODE_PROCESS_PHYSICS
	var player := _person("player", Vector3(3, 0, -2), PI / 2, idle, 30.0, 2.0, Vector3(0, 0, 0.3))
	player_skeleton = player[0]
	player_mod = player[1]
	npc_mod = _person("npc", Vector3(-4, 0, 5), 0.0, physics, -20.0, -3.0, Vector3(0, 0, -0.25))[1]


func _person(kind: String, at: Vector3, yaw: float, mode: int, start_deg: float,
		step_deg: float, head_offset: Vector3) -> Array:
	var body := Node3D.new()
	body.position = at
	body.rotation = Vector3(0, yaw, 0)
	var model := Node3D.new()
	model.name = "Model"
	body.add_child(model)
	var sk := Skeleton3D.new()
	sk.name = "Skeleton"
	for b in BONES:
		sk.add_bone(b[0])
	for i in range(BONES.size()):
		var parent: String = BONES[i][1]
		if parent != "":
			sk.set_bone_parent(i, sk.find_bone(parent))
		sk.set_bone_rest(i, Transform3D(Basis.IDENTITY, BONES[i][2]))
	sk.reset_bone_poses()
	sk.modifier_callback_mode_process = mode
	model.add_child(sk)
	var mod := Raise.new()
	mod.deg = start_deg
	mod.step_deg = step_deg
	mod.head_offset = head_offset
	sk.add_child(mod)
	body.add_to_group("entity")
	body.set_meta("entity_id", next_id)
	body.set_meta("kind", kind)
	body.set_meta("archetype", "office_worker")
	body.set_meta("faction", "civilian")
	next_id += 1
	add_child(body)
	return [sk, mod]


func _physics_process(_delta: float) -> void:
	arm_deg += 1
	var arm := player_skeleton.find_bone("RightUpperArm")
	player_skeleton.set_bone_pose_rotation(arm, Quaternion(Vector3(0, 0, 1), deg_to_rad(arm_deg)))


func state_report() -> Dictionary:
	return {"ok": true, "arm_deg": arm_deg, "player_deg": player_mod.deg, "npc_deg": npc_mod.deg}
