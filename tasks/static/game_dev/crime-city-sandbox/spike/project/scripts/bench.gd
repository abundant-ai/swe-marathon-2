class_name Bench
extends Node
## Item 3 benchmark role: build the block, spawn N cars and M people, run warm-up ticks, then
## time a window of ticks and print one JSON line. No probe needed (--fixed-fps keeps one
## physics tick per frame, so wall time per tick is the simulation cost).

var game: Node
var warmup := 300
var ticks := 3600
var n := 0
var t_start := 0
var tick_us: PackedInt64Array = PackedInt64Array()
var _last := 0


static func start(g: Node) -> void:
	var b := Bench.new()
	b.name = "Bench"
	b.game = g
	b.warmup = int(g.args.get("warmup", "300"))
	b.ticks = int(g.args.get("ticks", "3600"))
	g.main.add_child(b)
	var cars := int(g.args.get("cars", "40"))
	var peds := int(g.args.get("peds", "60"))
	g.world_reset({"seed": g.seed_value, "density": cars / 40.0, "ped_density": peds / 60.0})
	if g.args.get("noanim", "") == "true":
		for p in g.traffic.peds:
			p.anim.active = false
			p.anim.process_mode = Node.PROCESS_MODE_DISABLED


func _ready() -> void:
	process_physics_priority = -2147483000


func _physics_process(_dt: float) -> void:
	n += 1
	var now := Time.get_ticks_usec()
	if n == warmup:
		t_start = now
		print("BENCH_START")
	elif n > warmup:
		tick_us.append(now - _last)
	_last = now
	if n == warmup + ticks:
		var wall := (now - t_start) / 1e6
		var arr := Array(tick_us)
		arr.sort()
		var moving := 0
		for c in game.traffic.cars:
			if is_instance_valid(c) and c.linear_velocity.length() > 0.5:
				moving += 1
		var bones := 0
		for p in game.traffic.peds:
			if is_instance_valid(p):
				bones += p.skel.get_bone_count()
		var res := {"ticks": ticks, "wall_s": wall, "sim_s": ticks / 60.0, "speedup": (ticks / 60.0) / wall,
			"ms_mean": wall * 1000.0 / ticks, "ms_p50": arr[arr.size() / 2] / 1000.0,
			"ms_p95": arr[int(arr.size() * 0.95)] / 1000.0, "ms_max": arr[arr.size() - 1] / 1000.0,
			"cars": game.traffic.cars.size(), "cars_moving": moving, "peds": game.traffic.peds.size(),
			"ped_bones": bones, "art": game.art, "car_impl": game.car_impl,
			"nodes": Performance.get_monitor(Performance.OBJECT_NODE_COUNT),
			"objects": Performance.get_monitor(Performance.OBJECT_COUNT),
			"mem_static_mb": Performance.get_monitor(Performance.MEMORY_STATIC) / 1048576.0,
			"worker_threads": ProjectSettings.get_setting("threading/worker_pool/max_threads"),
			"physics_engine": ProjectSettings.get_setting("physics/3d/physics_engine")}
		print("BENCH_END ", JSON.stringify(res))
		get_tree().quit(0)
