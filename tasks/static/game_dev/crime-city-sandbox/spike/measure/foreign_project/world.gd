extends Node3D
# A capsule "robot" with a 3-bone arm. Bone names follow the humanoid profile for the arm only.
var body: CharacterBody3D
var sk: Skeleton3D
var arm_speed := 1.0
var angle := 0.0

func _ready() -> void:
	var floor := StaticBody3D.new()
	var fs := CollisionShape3D.new()
	var box := BoxShape3D.new()
	box.size = Vector3(100, 1, 100)
	fs.shape = box
	floor.add_child(fs)
	floor.position = Vector3(0, -0.5, 0)
	add_child(floor)
	body = CharacterBody3D.new()
	body.name = "Robot"
	var cs := CollisionShape3D.new()
	cs.shape = CapsuleShape3D.new()
	cs.position = Vector3(0, 1, 0)
	body.add_child(cs)
	var model := Node3D.new()
	model.name = "Model"
	var rig := Node3D.new()
	rig.name = "Rig"
	sk = Skeleton3D.new()
	for n in ["Hips", "RightUpperArm", "RightLowerArm", "RightHand"]:
		sk.add_bone(n)
	sk.set_bone_parent(1, 0)
	sk.set_bone_parent(2, 1)
	sk.set_bone_parent(3, 2)
	sk.set_bone_rest(0, Transform3D(Basis.IDENTITY, Vector3(0, 1.0, 0)))
	sk.set_bone_rest(1, Transform3D(Basis.IDENTITY, Vector3(-0.2, 0.4, 0)))
	sk.set_bone_rest(2, Transform3D(Basis.IDENTITY, Vector3(-0.3, 0, 0)))
	sk.set_bone_rest(3, Transform3D(Basis.IDENTITY, Vector3(-0.25, 0, 0)))
	sk.reset_bone_poses()
	rig.add_child(sk)
	model.add_child(rig)
	model.position = Vector3(0, 0, 0)
	body.add_child(model)
	add_child(body)
	body.position = Vector3(3, 0, 5)
	body.add_to_group("entity")
	body.set_meta("entity_id", 7)
	body.set_meta("kind", "player")
	body.set_meta("archetype", "robot")
	body.set_meta("faction", "player")

func _physics_process(dt: float) -> void:
	# arm: the upper arm turns about Z by arm_speed degrees per tick (analytic ground truth)
	angle += deg_to_rad(arm_speed)
	sk.set_bone_pose_rotation(1, Quaternion(Vector3(0, 0, 1), angle))
	var f := Input.get_action_strength("move_forward")
	body.velocity = Vector3(0, 0, -3.0 * f)
	body.move_and_slide()
