class_name SignalSystem
extends Node
## Fixed-time signals from the plan: one phase per approach, green -> amber -> all-red.
## Each signalised junction is an entity (kind "signal") whose "state" meta maps approach -> colour.

var plan: Plan
var ticks := 0
var junctions: Array = []
var states := {}
var left := {}


func _ready() -> void:
	process_physics_priority = -60


func setup(p_plan: Plan) -> void:
	plan = p_plan
	for jid in plan.junctions:
		var j: Dictionary = plan.junctions[jid]
		if not j["signalised"]:
			continue
		var sig: Dictionary = j["signal"]
		var per := float(sig["green_s"]) + float(sig["amber_s"]) + float(sig["all_red_s"])
		var node := Node3D.new()
		node.name = "Signal_" + jid
		node.position = j["p"]
		Game.static_root.add_child(node)
		Game.register_static(node, "signal", "signal_" + str(sig["phases"].size()) + "way", "city")
		junctions.append({"id": jid, "phases": sig["phases"], "green": float(sig["green_s"]),
			"amber": float(sig["amber_s"]), "allred": float(sig["all_red_s"]),
			"offset": float(sig["offset_s"]), "per": per, "cycle": per * sig["phases"].size(),
			"node": node})
	_update()


func reset() -> void:
	ticks = 0
	_update()


func state(approach_id: String) -> String:
	return states.get(approach_id, "green")


func time_left(approach_id: String) -> float:
	return left.get(approach_id, 0.0)


func _physics_process(_dt: float) -> void:
	ticks += 1
	_update()


func _update() -> void:
	var t := float(ticks) / Engine.physics_ticks_per_second
	for j in junctions:
		var tt := fposmod(t + float(j["offset"]), float(j["cycle"]))
		var per: float = j["per"]
		var k := int(tt / per)
		var u := tt - k * per
		var snap := {}
		for pi in range(j["phases"].size()):
			for ap in j["phases"][pi]:
				var st := "red"
				var lft := 0.0
				if pi == k:
					if u < j["green"]:
						st = "green"
						lft = j["green"] - u
					elif u < j["green"] + j["amber"]:
						st = "amber"
						lft = j["green"] + j["amber"] - u
					else:
						lft = per - u
				states[ap] = st
				left[ap] = lft
				snap[ap] = st
		j["node"].set_meta("state", snap)
