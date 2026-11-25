class_name CarVisual
extends RefCounted
## Car visuals: a box by default; the Kenney Car Kit model when the real-art mode is on and the
## model is imported. Visual only; collision stays the car's own box.

const KENNEY := {"sedan": "sedan", "police": "police", "taxi": "taxi"}
const KENNEY_DIR := "res://assets/vendor/kenney_car_kit/"
const KENNEY_SCALE := 1.72
static var _cache := {}
static var _box_mesh: BoxMesh


static func attach(car: Node3D, model: String, impl: String) -> void:
	var front_is_minus_z := impl != "vehicle_body"
	if Game.art != "primitive":
		var path: String = KENNEY_DIR + KENNEY.get(model, "sedan") + ".glb"
		if not _cache.has(path):
			_cache[path] = load(path) if ResourceLoader.exists(path) else null
		var ps: PackedScene = _cache[path]
		if ps != null:
			var inst := ps.instantiate()
			inst.name = "Visual"
			inst.scale = Vector3.ONE * KENNEY_SCALE
			inst.position = Vector3(0, -0.56, 0)
			if front_is_minus_z:
				inst.rotation.y = PI
			car.add_child(inst)
			return
	if _box_mesh == null:
		_box_mesh = BoxMesh.new()
		_box_mesh.size = Vector3(1.8, 0.9, 4.4)
	var mi := MeshInstance3D.new()
	mi.name = "Visual"
	mi.mesh = _box_mesh
	mi.position = Vector3(0, 0.3, 0)
	car.add_child(mi)
