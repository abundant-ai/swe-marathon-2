extends Node
## QA telemetry probe, GDScript prototype of the native probe (design 3.3).
## Inserted first in [autoload] under a random name; talks to the harness over 127.0.0.1 with
## length-prefixed JSON, each message signed with HMAC-SHA256 under a per-run key.
## Lockstep: at an observation tick it sends a frame and blocks until the next command, so the
## harness owns the clock. Inputs go in as InputEventAction through Input.parse_input_event().

var _tcp := StreamPeerTCP.new()
var _key := PackedByteArray()
var _on := false
var _left := 0
var _cmd_tick := 0
var _timeline := {}
var _events: Array = []
var _observe := {}
var _queries: Array = []
var _dev_results: Array = []
var _hooked := false
var _skel_cache := {}
var _last_frame_us := 0
var _ticks_since := 0
var _probe_us := 0
var _sent := 0
var _recv_n := 0
var _core = null              # native core (GDExtension) when present: key and socket live there


func _ready() -> void:
	process_physics_priority = -2000000000
	process_priority = -2000000000
	var port := int(OS.get_environment("QA_PROBE_PORT"))
	if port <= 0:
		set_physics_process(false)
		return
	var cls := OS.get_environment("QA_PROBE_CLASS")
	if cls != "" and ClassDB.class_exists(cls):
		_core = ClassDB.instantiate(cls)
		if not _core.connect_harness():
			push_error("qa probe: native core could not reach the harness")
			set_physics_process(false)
			return
		_on = true
		_send(_hello())
		return
	_key = OS.get_environment("QA_PROBE_KEY").hex_decode()
	_tcp.big_endian = true
	_tcp.connect_to_host("127.0.0.1", port)
	var t0 := Time.get_ticks_msec()
	while Time.get_ticks_msec() - t0 < 15000:
		_tcp.poll()
		if _tcp.get_status() == StreamPeerTCP.STATUS_CONNECTED:
			break
		OS.delay_msec(2)
	if _tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		push_error("qa probe: no harness")
		set_physics_process(false)
		return
	_tcp.set_no_delay(true)
	_on = true
	_send(_hello())


func _hello() -> Dictionary:
	return {"hello": {"engine": Engine.get_version_info()["string"],
		"native_core": _core != null, "key_in_environment": OS.get_environment("QA_PROBE_KEY") != "",
		"key_in_script": _key.size() > 0,
		"physics_engine": ProjectSettings.get_setting("physics/3d/physics_engine"),
		"ticks": Engine.physics_ticks_per_second, "jitter_fix": Engine.physics_jitter_fix,
		"separate_thread": ProjectSettings.get_setting("physics/3d/run_on_separate_thread"),
		"max_physics_steps": Engine.max_physics_steps_per_frame,
		"renderer": RenderingServer.get_current_rendering_method(),
		"display": DisplayServer.get_name(), "threads": OS.get_processor_count(),
		"worker_threads": ProjectSettings.get_setting("threading/worker_pool/max_threads"),
		"autoload_first": get_index() == 0}}


func _hook() -> void:
	_hooked = true
	var dc := get_tree().root.get_node_or_null("DevConsole")
	if dc != null and dc.has_signal("event"):
		dc.event.connect(_on_event)


func _on_event(n: String, d: Dictionary) -> void:
	_events.append({"t": Engine.get_physics_frames(), "n": n, "d": d})


func _physics_process(_dt: float) -> void:
	if not _on:
		return
	if not _hooked:
		_hook()
	var t := Engine.get_physics_frames()
	_ticks_since += 1
	if _left <= 0:
		var t0 := Time.get_ticks_usec()
		_send(_frame(t))
		var cmd := _recv()
		if cmd.is_empty():
			_on = false
			get_tree().quit(3)
			return
		_apply(cmd, t)
		_probe_us = Time.get_ticks_usec() - t0
	var off := t - _cmd_tick
	if _timeline.has(off):
		for ev in _timeline[off]:
			var e := InputEventAction.new()
			e.action = ev[0]
			e.strength = float(ev[1])
			e.pressed = float(ev[1]) > 0.0
			Input.parse_input_event(e)
		Input.flush_buffered_events()
	_left -= 1


func _apply(cmd: Dictionary, t: int) -> void:
	if cmd.get("quit", false):
		_on = false
		get_tree().quit(0)
		return
	_cmd_tick = t
	_left = maxi(1, int(cmd.get("run", 1)))
	_timeline.clear()
	for ev in cmd.get("inputs", []):
		var off := int(ev[0])
		if not _timeline.has(off):
			_timeline[off] = []
		_timeline[off].append([ev[1], ev[2]])
	_observe = cmd.get("observe", {})
	_queries = cmd.get("queries", [])
	var dc := get_tree().root.get_node_or_null("DevConsole")
	for d in cmd.get("dev", []):
		var res = {"ok": false, "error": "no DevConsole"}
		if dc != null:
			res = dc.exec(String(d[0]), d[1] if d.size() > 1 else {})
		_dev_results.append({"cmd": d[0], "res": res, "t": t})


func _frame(t: int) -> Dictionary:
	var now := Time.get_ticks_usec()
	var f := {"t": t, "events": _events, "dev": _dev_results,
		"perf": {"ticks": _ticks_since, "wall_us": now - _last_frame_us if _last_frame_us > 0 else 0,
			"probe_us": _probe_us, "physics_ms": Performance.get_monitor(Performance.TIME_PHYSICS_PROCESS) * 1000.0,
			"objects": Performance.get_monitor(Performance.OBJECT_COUNT),
			"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
			"mem_static": Performance.get_monitor(Performance.MEMORY_STATIC)}}
	_last_frame_us = now
	_ticks_since = 0
	_events = []
	_dev_results = []
	var cam := get_viewport().get_camera_3d()
	var want_view: bool = _observe.get("in_view", false)
	if _observe.get("census", true):
		var census: Array = []
		for n in get_tree().get_nodes_in_group("entity"):
			census.append(_entity(n, cam if want_view else null))
		f["census"] = census
	if _observe.has("bones"):
		f["bones"] = _bones(_observe["bones"])
	if _observe.get("camera", false) and cam != null:
		var o := cam.global_position
		var z := cam.global_basis.z
		f["camera"] = {"p": [o.x, o.y, o.z], "bz": [z.x, z.y, z.z], "fov": cam.fov}
	if _observe.get("hud", false):
		var hud := {}
		for g in ["hud_wanted"]:
			var nodes := get_tree().get_nodes_in_group(g)
			if nodes.is_empty():
				continue
			var vis := 0
			for c in nodes[0].get_children():
				if c is CanvasItem and c.is_visible_in_tree():
					vis += 1
			hud[g] = vis
		f["hud"] = hud
	if _observe.get("state", false):
		var dc := get_tree().root.get_node_or_null("DevConsole")
		if dc != null:
			f["state"] = dc.exec("state", {}).get("state", {})
	if not _queries.is_empty():
		f["q"] = _run_queries(_queries)
		_queries = []
	return f


func _entity(n: Node, cam: Camera3D) -> Dictionary:
	var e := {"id": n.get_meta("entity_id", -1), "k": n.get_meta("kind", ""),
		"a": n.get_meta("archetype", ""), "f": n.get_meta("faction", "")}
	if n is Node3D:
		var p: Vector3 = n.global_position
		var bz: Vector3 = n.global_basis.z
		e["p"] = [p.x, p.y, p.z]
		e["bz"] = [bz.x, bz.y, bz.z]
		e["up"] = n.global_basis.y.y
		if n is RigidBody3D:
			var v: Vector3 = PhysicsServer3D.body_get_state(n.get_rid(), PhysicsServer3D.BODY_STATE_LINEAR_VELOCITY)
			e["v"] = [v.x, v.y, v.z]
		if cam != null:
			e["iv"] = cam.is_position_in_frustum(p + Vector3(0, 1.0, 0))
	if "vehicle" in n and n.vehicle != null and is_instance_valid(n.vehicle):
		e["veh"] = n.vehicle.get_meta("entity_id", -1)
		e["seat"] = n.seat
	if n.has_meta("state"):
		e["st"] = n.get_meta("state")
	return e


func _skeleton_of(n: Node) -> Skeleton3D:
	var id: int = n.get_meta("entity_id", -1)
	if _skel_cache.has(id) and is_instance_valid(_skel_cache[id]):
		return _skel_cache[id]
	var found := n.find_children("*", "Skeleton3D", true, false)
	var sk: Skeleton3D = found[0] if found.size() > 0 else null
	_skel_cache[id] = sk
	return sk


func _bones(spec: Dictionary) -> Dictionary:
	var out := {}
	var ids: Array = []
	for x in spec.get("ids", []):
		ids.append(int(x))
	var names: Array = spec.get("names", [])
	for n in get_tree().get_nodes_in_group("entity"):
		var id: int = n.get_meta("entity_id", -1)
		if not ids.has(id):
			continue
		var sk := _skeleton_of(n)
		if sk == null:
			continue
		var gx := sk.global_transform
		var m := {}
		var list: Array = names
		if list.is_empty():
			for i in range(sk.get_bone_count()):
				list.append(sk.get_bone_name(i))
		for bn in list:
			var bi := sk.find_bone(bn)
			if bi < 0:
				continue
			var p := gx * sk.get_bone_global_pose(bi).origin
			m[bn] = [p.x, p.y, p.z]
		out[str(id)] = m
	return out


func _space() -> PhysicsDirectSpaceState3D:
	return get_viewport().find_world_3d().direct_space_state


func _ray(space: PhysicsDirectSpaceState3D, a: Vector3, b: Vector3, mask: int) -> Dictionary:
	var q := PhysicsRayQueryParameters3D.create(a, b, mask)
	var h := space.intersect_ray(q)
	if h.is_empty():
		return {"hit": false}
	var c = h["collider"]
	var hp: Vector3 = h["position"]
	var r := {"hit": true, "p": [hp.x, hp.y, hp.z]}
	if c != null:
		r["surface"] = c.get_meta("surface", "")
		if c.has_meta("entity_id"):
			r["entity"] = c.get_meta("entity_id")
		elif c.get_parent() != null and c.get_parent().has_meta("entity_id"):
			r["entity"] = c.get_parent().get_meta("entity_id")
		if c.has_meta("parcel"):
			r["parcel"] = c.get_meta("parcel")
	return r


func _run_queries(qs: Array) -> Dictionary:
	var out := {}
	var space := _space()
	for q in qs:
		var qid: String = q.get("id", "q")
		match String(q.get("type", "")):
			"ray":
				var a: Array = q["from"]
				var b: Array = q["to"]
				out[qid] = _ray(space, Vector3(a[0], a[1], a[2]), Vector3(b[0], b[1], b[2]), int(q.get("mask", 1)))
			"down":
				var res: Array = []
				var y0 := float(q.get("y0", 80.0))
				var y1 := float(q.get("y1", -5.0))
				for pt in q["points"]:
					var r := _ray(space, Vector3(pt[0], y0, pt[1]), Vector3(pt[0], y1, pt[1]), int(q.get("mask", 1)))
					res.append([r["p"][1], r.get("surface", ""), r.get("parcel", "")] if r["hit"] else null)
				out[qid] = res
			"los":
				var ea = _entity_by_id(int(q["a"]))
				var eb = _entity_by_id(int(q["b"]))
				if ea == null or eb == null:
					out[qid] = {"ok": false}
					continue
				var pa: Vector3 = ea.global_position + Vector3(0, float(q.get("a_up", 1.65)), 0)
				var pb: Vector3 = eb.global_position + Vector3(0, float(q.get("b_up", 0.8)), 0)
				var sk := _skeleton_of(ea)
				if sk != null and sk.find_bone("Head") >= 0:
					pa = sk.global_transform * sk.get_bone_global_pose(sk.find_bone("Head")).origin
				var r2 := _ray(space, pa, pb, int(q.get("mask", 1)))
				out[qid] = {"ok": true, "clear": not r2["hit"], "from": [pa.x, pa.y, pa.z], "dist": pa.distance_to(pb)}
			"skeleton":
				var en = _entity_by_id(int(q["id_entity"]))
				out[qid] = _skeleton_info(en)
			"unregistered":
				out[qid] = _unregistered()
	return out


func _entity_by_id(id: int) -> Node:
	for n in get_tree().get_nodes_in_group("entity"):
		if int(n.get_meta("entity_id", -1)) == id:
			return n
	return null


func _skeleton_info(n: Node) -> Dictionary:
	if n == null:
		return {"ok": false}
	var sks := n.find_children("*", "Skeleton3D", true, false)
	if sks.is_empty():
		return {"ok": true, "skeletons": 0}
	var sk: Skeleton3D = sks[0]
	var names: Array = []
	for i in range(sk.get_bone_count()):
		names.append(sk.get_bone_name(i))
	var bound := 0
	var tris := 0
	for mi in n.find_children("*", "MeshInstance3D", true, false):
		if mi.skin != null and mi.get_node_or_null(mi.skeleton) == sk and mi.mesh != null:
			var has_bones := false
			for s in range(mi.mesh.get_surface_count()):
				var arr: Array = mi.mesh.surface_get_arrays(s)
				if arr[Mesh.ARRAY_BONES] != null and arr[Mesh.ARRAY_BONES].size() > 0:
					has_bones = true
				if arr[Mesh.ARRAY_INDEX] != null:
					tris += arr[Mesh.ARRAY_INDEX].size() / 3
			if has_bones:
				bound += 1
	return {"ok": true, "skeletons": sks.size(), "bones": names, "bound_meshes": bound, "triangles": tris}


func _unregistered() -> Array:
	var out: Array = []
	for cls in ["Skeleton3D", "CharacterBody3D", "VehicleBody3D"]:
		for n in get_tree().root.find_children("*", cls, true, false):
			var e: Node = n
			var registered := false
			while e != null:
				if e.is_in_group("entity"):
					registered = true
					break
				e = e.get_parent()
			if not registered:
				out.append(str(n.get_path()))
	return out


func _mac(payload: PackedByteArray) -> PackedByteArray:
	var h := HMACContext.new()
	h.start(HashingContext.HASH_SHA256, _key)
	h.update(payload)
	return h.finish()


func _send(obj: Dictionary) -> void:
	if _core != null:
		_core.send(JSON.stringify(obj, "", false, true))
		_sent += 1
		return
	var payload := JSON.stringify(obj, "", false, true).to_utf8_buffer()
	var mac := _mac(payload)
	_tcp.put_u32(payload.size() + 32)
	_tcp.put_data(mac)
	_tcp.put_data(payload)
	_sent += 1


func _recv() -> Dictionary:
	if _core != null:
		var text: String = _core.recv()
		if text == "":
			return {}
		_recv_n += 1
		var p = JSON.parse_string(text)
		return p if p is Dictionary else {}
	var n := _tcp.get_u32()
	if n < 32 or _tcp.get_status() != StreamPeerTCP.STATUS_CONNECTED:
		return {}
	var r := _tcp.get_data(n)
	if r[0] != OK:
		return {}
	var data: PackedByteArray = r[1]
	var mac := data.slice(0, 32)
	var payload := data.slice(32)
	if _mac(payload) != mac:
		push_error("qa probe: bad signature")
		return {}
	_recv_n += 1
	var parsed = JSON.parse_string(payload.get_string_from_utf8())
	return parsed if parsed is Dictionary else {}
