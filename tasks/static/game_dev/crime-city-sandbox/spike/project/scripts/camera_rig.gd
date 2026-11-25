class_name CameraRig
extends Node
## Third-person camera: behind the player on foot (yaw from look actions), behind the car when
## driving. Runs after gameplay in the physics tick.

func _ready() -> void:
	process_physics_priority = 100


func _physics_process(_dt: float) -> void:
	var pl: Person = Game.player
	var cam := Game.camera
	if pl == null or not is_instance_valid(pl) or cam == null:
		return
	var target: Vector3
	var back: Vector3
	var height := 2.0
	var dist := 4.0
	if pl.vehicle != null and is_instance_valid(pl.vehicle):
		var f: Vector3 = pl.vehicle.fwd()
		f.y = 0.0
		back = -f.normalized()
		target = pl.vehicle.global_position + Vector3(0, 1.0, 0)
		height = 3.0
		dist = 7.5
	else:
		back = -Vector3(-sin(pl.cam_yaw), 0.0, -cos(pl.cam_yaw))
		target = pl.global_position + Vector3(0, 1.5, 0)
	var pos := target + back * dist + Vector3(0, height - 1.0, 0)
	cam.global_position = pos
	if pos.distance_to(target) > 0.01:
		cam.look_at(target, Vector3.UP)
