class_name CarInput
extends RefCounted
## Player driving through the InputMap actions only.

static func read_player(car) -> void:
	var acc := Input.get_action_strength("accelerate")
	var brk := Input.get_action_strength("brake")
	car.in_steer = Input.get_action_strength("steer_left") - Input.get_action_strength("steer_right")
	car.in_handbrake = Input.is_action_pressed("handbrake")
	var v: float = car.speed()
	# reverse only after the brake has been held at a standstill for 0.6 s
	if brk > 0.05 and acc < 0.05 and v < 0.3:
		car.rev_hold += 1.0 / Engine.physics_ticks_per_second
	elif brk <= 0.05:
		car.rev_hold = 0.0
	if car.rev_hold > 0.6:
		car.in_reverse = true
		car.in_throttle = brk
		car.in_brake = 0.0
	else:
		car.in_reverse = false
		car.in_throttle = acc
		car.in_brake = brk
