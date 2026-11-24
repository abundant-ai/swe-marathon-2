class_name LaneDriver
extends Node
## AI driver for one car: follows plan lane centrelines (pure pursuit), keeps a gap (IDM),
## obeys signals, and in pursuit mode routes to a target over the lane graph.

var car                        # RaycastCar or VBCar (parent)
var plan: Plan
var rng := RandomNumberGenerator.new()
var path: Array = []
var seg_i := 0
var s := 0.0
var lat := 0.0
var mode := "traffic"          # traffic | pursuit
var target: Node3D = null
var obey_signals := true
var v_limit := 13.9
var replan_left := 0.0
var direct := false
var amber_go := {}             # approach id -> decision latched for this amber
var last_gap := 999.0
var _ray := PhysicsRayQueryParameters3D.new()

const CAR_LEN := 4.6
const A_MAX := 2.0
const B_COMF := 3.0
const S0 := 2.0
const T_HEAD := 1.2


func _ready() -> void:
	process_physics_priority = -20
	_ray.collision_mask = 2 | 4 | 16
	_ray.exclude = [car.get_rid()]


func start_on(seg_id: String, s0: float) -> void:
	path = [seg_id]
	seg_i = 0
	s = s0
	if mode == "traffic":
		_extend()


func _extend() -> void:
	while path.size() - seg_i < 5:
		var last: Plan.Seg = plan.segs[path[path.size() - 1]]
		if last.next.is_empty():
			break
		path.append(last.next[rng.randi() % last.next.size()])
	if seg_i > 10:
		path = path.slice(seg_i - 2)
		seg_i = 2


func current_seg() -> Plan.Seg:
	return plan.segs[path[seg_i]]


func _point_ahead(dist: float) -> Vector3:
	var i := seg_i
	var ss := s + dist
	while i < path.size():
		var sg: Plan.Seg = plan.segs[path[i]]
		if ss <= sg.length or i == path.size() - 1:
			return sg.point_at(ss)
		ss -= sg.length
		i += 1
	return plan.segs[path[path.size() - 1]].point_at(ss)


func _physics_process(dt: float) -> void:
	if car == null or path.is_empty():
		return
	var pos: Vector3 = car.global_position
	var v: float = car.speed()
	if mode == "pursuit":
		_pursuit_update(dt, pos)
		if direct:
			_drive_direct(pos, v)
			return
	var sg := current_seg()
	var pr := sg.project(pos)
	s = pr.x
	lat = pr.y
	while s >= sg.length - 0.05 and seg_i < path.size() - 1:
		seg_i += 1
		sg = current_seg()
		pr = sg.project(pos)
		s = pr.x
		lat = pr.y
	if mode == "traffic":
		_extend()
	# steering: pure pursuit on the path
	var ld := clampf(4.0 + 0.55 * absf(v), 5.0, 16.0)
	var loc: Vector2 = car.flat_local(_point_ahead(ld))
	var curv := 2.0 * loc.y / maxf(loc.length_squared(), 0.01)
	var delta := atan(car.wheelbase * curv)
	car.in_steer = clampf(delta / car.max_steer_at(v), -1.0, 1.0)
	# speed target from limits and upcoming curvature
	var vt := minf(v_limit, sg.vmax)
	var acc_d := sg.length - s
	for k in range(seg_i + 1, path.size()):
		var nx: Plan.Seg = plan.segs[path[k]]
		vt = minf(vt, sqrt(nx.vmax * nx.vmax + 2.0 * 2.2 * maxf(acc_d - 2.0, 0.0)))
		acc_d += nx.length
		if acc_d > 60.0:
			break
	var lead: Vector2 = Game.traffic.leader_gap(self)
	var gap := lead.x
	var vl := lead.y
	# stop line
	if obey_signals and sg.kind == "lane":
		var ap: Dictionary = plan.approaches.get(sg.approach, {})
		if not ap.is_empty() and ap["signalised"]:
			var st: String = Game.signals.state(sg.approach)
			var to_line := sg.length - s - CAR_LEN * 0.5
			var stop := st == "red"
			if st == "amber":
				if not amber_go.has(sg.approach):
					var left: float = Game.signals.time_left(sg.approach)
					amber_go[sg.approach] = to_line < 0.5 or (to_line / maxf(v, 0.1) < left - 0.3 and to_line < v * v / (2.0 * B_COMF) + 2.0)
				stop = not amber_go[sg.approach]
			elif st == "green":
				amber_go.erase(sg.approach)
			if stop and to_line > -0.5 and to_line < gap:
				gap = maxf(to_line, 0.0)
				vl = 0.0
	# obstacles straight ahead (player, police, props, people)
	var f: Vector3 = car.fwd()
	_ray.from = pos + f * (CAR_LEN * 0.5 + 0.1) + Vector3(0, 0.5, 0)
	_ray.to = _ray.from + f * maxf(8.0, v * 2.2 + 4.0)
	var hit: Dictionary = car.get_world_3d().direct_space_state.intersect_ray(_ray)
	if not hit.is_empty():
		var hd: float = _ray.from.distance_to(hit["position"])
		if hd < gap:
			gap = hd
			vl = 0.0
	last_gap = gap
	var a := _idm(v, vt, gap, vl)
	_apply_accel(a, v, vt)


func _idm(v: float, vt: float, gap: float, vl: float) -> float:
	var free := 1.0 - pow(maxf(v, 0.0) / maxf(vt, 0.5), 4.0)
	if gap > 120.0:
		return clampf(A_MAX * free, -8.0, A_MAX)
	var ss := S0 + maxf(0.0, v * T_HEAD + v * (v - vl) / (2.0 * sqrt(A_MAX * B_COMF)))
	var a := A_MAX * (free - pow(ss / maxf(gap, 0.1), 2.0))
	if gap < 0.8:
		a = -8.0
	return clampf(a, -8.0, A_MAX)


func _apply_accel(a: float, v: float, vt: float) -> void:
	car.in_reverse = false
	if vt < 0.3 and v < 0.6 and a <= 0.0:
		car.in_throttle = 0.0
		car.in_brake = 0.6
		return
	if a > 0.05:
		car.in_throttle = clampf(a / 3.2 + 0.04 * v / 10.0, 0.0, 1.0)
		car.in_brake = 0.0
	elif a < -0.25:
		car.in_throttle = 0.0
		car.in_brake = clampf(-a / 8.5, 0.0, 1.0)
	else:
		car.in_throttle = 0.0
		car.in_brake = 0.0


# ---------------------------------------------------------------- pursuit

func _pursuit_update(dt: float, pos: Vector3) -> void:
	if target == null or not is_instance_valid(target):
		return
	var tp := target.global_position
	var d := Vector2(tp.x - pos.x, tp.z - pos.z).length()
	direct = d < 32.0
	replan_left -= dt
	if not direct and replan_left <= 0.0:
		replan_left = 1.0
		var goal := plan.nearest_lane(tp, 60.0, ["lane"])
		var here := plan.nearest_lane(pos, 30.0, ["lane", "conn"])
		if goal.is_empty() or here.is_empty():
			return
		var cur_id: String = path[seg_i] if seg_i < path.size() else here["lane"]
		var r := plan.route(cur_id, goal["lane"])
		if r.is_empty():
			r = plan.route(here["lane"], goal["lane"])
		if not r.is_empty():
			path = r
			seg_i = 0


func _drive_direct(pos: Vector3, v: float) -> void:
	var tp := target.global_position
	var loc: Vector2 = car.flat_local(tp)
	var d := loc.length()
	var curv := 2.0 * loc.y / maxf(loc.length_squared(), 0.01)
	car.in_steer = clampf(atan(car.wheelbase * curv) / car.max_steer_at(v), -1.0, 1.0)
	var vt := clampf((d - 9.0) * 0.6, 0.0, 10.0)
	if loc.x < 0.0:
		vt = minf(vt, 3.0)
	var a := clampf((vt - v) * 1.5, -8.0, A_MAX)
	_apply_accel(a, v, vt)
