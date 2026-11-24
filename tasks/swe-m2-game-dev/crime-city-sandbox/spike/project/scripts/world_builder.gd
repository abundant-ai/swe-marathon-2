class_name WorldBuilder
extends RefCounted
## Builds the static world (ground, roads, raised blocks with sidewalks, buildings, street
## lights) from a Plan. Collision is on layer 1 (world); each body carries a "surface" meta.

const ROAD_THICK := 0.4

static var _mats := {}


static func _mat(key: String, col: Color) -> StandardMaterial3D:
	if not _mats.has(key):
		var m := StandardMaterial3D.new()
		m.albedo_color = col
		_mats[key] = m
	return _mats[key]


static func _box(parent: Node3D, name: String, center: Vector3, size: Vector3, yaw: float,
		surface: String, mat: Material, layer := 1) -> StaticBody3D:
	var body := StaticBody3D.new()
	body.name = name
	body.collision_layer = layer
	body.collision_mask = 0
	body.set_meta("surface", surface)
	var cs := CollisionShape3D.new()
	var sh := BoxShape3D.new()
	sh.size = size
	cs.shape = sh
	body.add_child(cs)
	var mi := MeshInstance3D.new()
	var bm := BoxMesh.new()
	bm.size = size
	mi.mesh = bm
	mi.material_override = mat
	body.add_child(mi)
	body.transform = Transform3D(Basis(Vector3.UP, yaw), center)
	parent.add_child(body)
	return body


static func build(plan: Plan, root: Node3D, opts := {}) -> Dictionary:
	var stats := {"bodies": 0, "lights": 0}
	# ground: top at -0.05, big enough for the proving ground
	_box(root, "Ground", Vector3(0, -1.05, 0), Vector3(3200, 2.0, 3200), 0.0, "ground",
		_mat("ground", Color(0.35, 0.42, 0.3)))
	stats["bodies"] += 1
	# roads: one slab per edge, node to node plus the junction box at each end
	for eid in plan.edges:
		var e: Dictionary = plan.edges[eid]
		var mid: Vector3 = (e["pa"] + e["pb"]) * 0.5
		var width: float = float(e["per_dir"]) * 2.0 * float(e["lane_w"])
		var length: float = float(e["length"]) + width
		var yaw := atan2(e["dir"].x, e["dir"].z)
		mid.y = float(e["elev"]) - ROAD_THICK * 0.5
		_box(root, "Road_" + eid, mid, Vector3(width, ROAD_THICK, length), yaw, "road",
			_mat("road", Color(0.18, 0.18, 0.2)))
		stats["bodies"] += 1
	# raised blocks: sidewalks are their outer band
	for b in plan.blocks:
		var poly: Array = b["poly"]
		var x0: float = poly[0][0]
		var z0: float = poly[0][1]
		var x1: float = poly[2][0]
		var z1: float = poly[2][1]
		var elev := float(b["elevation_m"])
		var thick := 0.6
		_box(root, "Block_" + b["id"], Vector3((x0 + x1) * 0.5, elev - thick * 0.5, (z0 + z1) * 0.5),
			Vector3(absf(x1 - x0), thick, absf(z1 - z0)), 0.0, "sidewalk",
			_mat("walk", Color(0.6, 0.6, 0.58)))
		stats["bodies"] += 1
	# buildings
	for p in plan.parcels:
		var poly2: Array = p["poly"]
		var sb := float(p["setback_m"])
		var px0: float = float(poly2[0][0]) + sb
		var pz0: float = float(poly2[0][1]) + sb
		var px1: float = float(poly2[2][0]) - sb
		var pz1: float = float(poly2[2][1]) - sb
		var base := float(p["base_m"])
		var h := float(p["height_m"])
		var body := _box(root, "Bldg_" + p["id"], Vector3((px0 + px1) * 0.5, base + h * 0.5, (pz0 + pz1) * 0.5),
			Vector3(px1 - px0, h, pz1 - pz0), 0.0, "building",
			_mat("bldg_" + p["zoning"], Color(0.55, 0.5, 0.62) if p["zoning"] == "commercial" else Color(0.7, 0.55, 0.45)))
		body.set_meta("parcel", p["id"])
		stats["bodies"] += 1
	# street lights along each edge, both sides, every 40 m
	if opts.get("lights", true):
		for eid2 in plan.edges:
			var e2: Dictionary = plan.edges[eid2]
			var t: Vector3 = e2["dir"]
			var right := Vector3(-t.z, 0.0, t.x)
			var half_w: float = float(e2["per_dir"]) * float(e2["lane_w"])
			var n := int(float(e2["length"]) / 40.0)
			for k in range(1, n):
				for side in [-1.0, 1.0]:
					var lp: Vector3 = e2["pa"] + t * (k * 40.0) + right * side * (half_w + 1.2)
					lp.y = 5.0
					var light := OmniLight3D.new()
					light.name = "Lamp_%s_%d_%d" % [eid2, k, int(side)]
					light.omni_range = 18.0
					light.position = lp
					light.add_to_group("street_light")
					root.add_child(light)
					stats["lights"] += 1
	return stats
