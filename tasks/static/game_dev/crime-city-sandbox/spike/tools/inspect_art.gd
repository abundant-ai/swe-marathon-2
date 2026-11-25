extends SceneTree
## Prints what the import produced for the rigged files (item 8): skeleton names, bone names,
## library track paths, loop modes and root-motion speeds.

func _init() -> void:
	var body: PackedScene = load("res://assets/vendor/ubc/Superhero_Male_FullBody.gltf")
	var inst := body.instantiate()
	var sks := inst.find_children("*", "Skeleton3D", true, false)
	print("body root=", inst.name, " skeletons=", sks.size())
	for sk in sks:
		print("  skeleton path=", inst.get_path_to(sk), " unique=", sk.is_unique_name_in_owner(), " bones=", sk.get_bone_count())
		var names := []
		for i in range(sk.get_bone_count()):
			names.append(sk.get_bone_name(i))
		print("  bones: ", ", ".join(names))
		var head: int = sk.find_bone("Head")
		var toes: int = sk.find_bone("LeftToes")
		sk.reset_bone_poses()
		print("  rest Head y=", sk.get_bone_global_rest(head).origin.y if head >= 0 else -1.0, " LeftToes y=", sk.get_bone_global_rest(toes).origin.y if toes >= 0 else -1.0)
	for mi in inst.find_children("*", "MeshInstance3D", true, false):
		var tris := 0
		for s in range(mi.mesh.get_surface_count()):
			var arr: Array = mi.mesh.surface_get_arrays(s)
			tris += arr[Mesh.ARRAY_INDEX].size() / 3 if arr[Mesh.ARRAY_INDEX] != null else 0
		print("  mesh ", mi.name, " skin=", mi.skin != null, " skeleton=", mi.skeleton, " tris=", tris, " surfaces=", mi.mesh.get_surface_count())
	for lib_path in ["res://assets/vendor/ual/UAL1_Standard.glb", "res://assets/vendor/ual/UAL1_Standard_RM.glb"]:
		var lib: AnimationLibrary = load(lib_path)
		var names2 := lib.get_animation_list()
		print(lib_path, " clips=", names2.size())
		for cn in ["Walk", "Jog_Fwd", "Sprint", "Idle", "Driving", "Swim_Fwd", "Walk_Formal"]:
			if not lib.has_animation(cn):
				print("  missing ", cn)
				continue
			var a := lib.get_animation(cn)
			var paths := []
			for t in range(mini(4, a.get_track_count())):
				paths.append(str(a.track_get_path(t)) + "(" + str(a.track_get_type(t)) + ")")
			var root_t := a.find_track(NodePath("%GeneralSkeleton:Root"), Animation.TYPE_POSITION_3D)
			var speed := -1.0
			if root_t >= 0:
				var p0 := a.position_track_interpolate(root_t, 0.0)
				var p1 := a.position_track_interpolate(root_t, a.length)
				speed = Vector2(p1.x - p0.x, p1.z - p0.z).length() / a.length
			print("  ", cn, " len=", snappedf(a.length, 0.001), " loop=", a.loop_mode, " tracks=", a.get_track_count(), " root_speed=", snappedf(speed, 0.001), " first=", paths)
	quit()
