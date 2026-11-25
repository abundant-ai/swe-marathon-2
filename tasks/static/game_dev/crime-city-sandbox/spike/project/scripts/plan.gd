class_name Plan
extends RefCounted
## Loads a plan file and derives lanes, junction connectors, approaches, stop lines and
## anchors from it, following the "conventions" block of the plan.

class Seg:
	var id: String
	var kind: String = "lane"        # "lane" or "conn"
	var pts := PackedVector3Array()
	var cum := PackedFloat64Array()
	var length := 0.0
	var next: Array = []             # ids of segments that may follow
	var speed_mps := 13.9
	var vmax := 13.9                 # curvature-limited speed
	var approach := ""               # lanes: approach at the lane end
	var junction := ""               # lanes: end junction; connectors: their junction
	var start_junction := ""
	var turn := ""                   # connectors: left / straight / right
	var index := 0
	var edge := ""

	func finalize() -> void:
		cum.resize(pts.size())
		var acc := 0.0
		cum[0] = 0.0
		for i in range(1, pts.size()):
			acc += pts[i].distance_to(pts[i - 1])
			cum[i] = acc
		length = acc

	func point_at(s: float) -> Vector3:
		if s <= 0.0:
			return pts[0] + tangent_at(0.0) * s
		if s >= length:
			return pts[pts.size() - 1] + tangent_at(length) * (s - length)
		var i := _index_at(s)
		var seg_len: float = cum[i + 1] - cum[i]
		var u: float = (s - cum[i]) / maxf(seg_len, 1e-6)
		return pts[i].lerp(pts[i + 1], u)

	func tangent_at(s: float) -> Vector3:
		var i := _index_at(clampf(s, 0.0, length))
		return (pts[i + 1] - pts[i]).normalized()

	func _index_at(s: float) -> int:
		var n := pts.size()
		for i in range(n - 1):
			if s <= cum[i + 1]:
				return i
		return n - 2

	## Returns Vector2(s, lateral) where lateral > 0 means to the right of the direction of travel.
	func project(p: Vector3) -> Vector2:
		var best_d := INF
		var best := Vector2.ZERO
		for i in range(pts.size() - 1):
			var a := pts[i]
			var b := pts[i + 1]
			var ab := Vector3(b.x - a.x, 0.0, b.z - a.z)
			var ap := Vector3(p.x - a.x, 0.0, p.z - a.z)
			var l2 := ab.length_squared()
			var u := clampf(ap.dot(ab) / maxf(l2, 1e-9), 0.0, 1.0)
			# allow extrapolation past the ends of the polyline
			if i == 0:
				u = minf(ap.dot(ab) / maxf(l2, 1e-9), u)
			if i == pts.size() - 2:
				u = maxf(ap.dot(ab) / maxf(l2, 1e-9), u)
			var q := a + (b - a) * u
			var d := Vector2(p.x - q.x, p.z - q.z).length()
			if d < best_d:
				best_d = d
				var t := ab.normalized()
				var right := Vector3(-t.z, 0.0, t.x)
				var lat := Vector3(p.x - q.x, 0.0, p.z - q.z).dot(right)
				best = Vector2(cum[i] + u * sqrt(l2), lat)
		return best

var data: Dictionary
var nodes := {}          # id -> Vector3
var edges := {}          # id -> Dictionary
var segs := {}           # id -> Seg
var lane_ids: Array = []
var approaches := {}     # id -> Dictionary
var junctions := {}      # id -> Dictionary
var pois := {}           # id -> Dictionary
var sidewalks: Array = []
var parcels: Array = []
var blocks: Array = []


static func load_file(path: String) -> Plan:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		push_error("plan: cannot open %s" % path)
		return null
	var parsed = JSON.parse_string(f.get_as_text())
	var p := Plan.new()
	p._build(parsed)
	return p


static func _v3(a) -> Vector3:
	return Vector3(float(a[0]), float(a[1]), float(a[2]))


func _build(d: Dictionary) -> void:
	data = d
	for n in d["nodes"]:
		nodes[n["id"]] = _v3(n["p"])
	for j in d["intersections"]:
		junctions[j["id"]] = {
			"id": j["id"], "p": nodes[j["node"]], "signalised": bool(j["signalised"]),
			"box_half": float(j["box_half_m"]), "stop_line_m": float(j["stop_line_m"]),
			"approaches": [], "signal": j.get("signal", {}),
		}
	# lanes
	for e in d["edges"]:
		var pa: Vector3 = nodes[e["a"]]
		var pb: Vector3 = nodes[e["b"]]
		var dvec := (pb - pa)
		dvec.y = 0.0
		var length := dvec.length()
		var dirn := dvec / length
		var lw := float(e["lane_width_m"])
		var elev := float(e["elevation_m"])
		var info := {"id": e["id"], "a": e["a"], "b": e["b"], "pa": pa, "pb": pb, "dir": dirn,
			"length": length, "lane_w": lw, "elev": elev, "speed": float(e["speed_kmh"]) / 3.6,
			"lanes": e["lanes"], "per_dir": 0}
		var per_dir := 0
		for ln in e["lanes"]:
			if ln["dir"] == "ab":
				per_dir += 1
		info["per_dir"] = per_dir
		edges[e["id"]] = info
		for ln in e["lanes"]:
			var forward: bool = ln["dir"] == "ab"
			var start_node: String = e["a"] if forward else e["b"]
			var end_node: String = e["b"] if forward else e["a"]
			var t := dirn if forward else -dirn
			var right := Vector3(-t.z, 0.0, t.x)
			var off := right * ((int(ln["index"]) + 0.5) * lw)
			var ps: Vector3 = nodes[start_node]
			var pe: Vector3 = nodes[end_node]
			var sl_start: float = junctions[start_node]["stop_line_m"]
			var sl_end: float = junctions[end_node]["stop_line_m"]
			var sg := Seg.new()
			sg.id = ln["id"]
			sg.kind = "lane"
			sg.index = int(ln["index"])
			sg.edge = e["id"]
			sg.speed_mps = info["speed"]
			sg.vmax = sg.speed_mps
			sg.junction = end_node
			sg.start_junction = start_node
			sg.approach = "%s<%s" % [end_node, e["id"]]
			var p0 := ps + t * sl_start + off
			var p1 := pe - t * sl_end + off
			p0.y = elev
			p1.y = elev
			sg.pts = PackedVector3Array([p0, p1])
			sg.finalize()
			segs[sg.id] = sg
			lane_ids.append(sg.id)
	# approaches (one per incoming direction of an edge at a junction)
	for j in d["intersections"]:
		for ap in j["approaches"]:
			var e: Dictionary = edges[ap["edge"]]
			var forward: bool = ap["dir"] == "ab"
			var t: Vector3 = e["dir"] if forward else -e["dir"]
			var jp: Vector3 = nodes[j["node"]]
			var lanes: Array = []
			for ln in e["lanes"]:
				if ln["dir"] == ap["dir"]:
					lanes.append(ln["id"])
			var stop_p := jp - t * float(j["stop_line_m"])
			stop_p.y = e["elev"]
			approaches[ap["id"]] = {"id": ap["id"], "junction": j["id"], "edge": ap["edge"],
				"dir": ap["dir"], "lanes": lanes, "fwd": t, "right": Vector3(-t.z, 0.0, t.x),
				"stop_p": stop_p, "half_w": float(e["per_dir"]) * float(e["lane_w"]),
				"signalised": bool(j["signalised"])}
			junctions[j["id"]]["approaches"].append(ap["id"])
	_build_connectors()
	for p in d["pois"]:
		var e2: Dictionary = p.duplicate(true)
		e2["pos"] = _v3(p["p"])
		pois[p["id"]] = e2
	for s in d["sidewalks"]:
		var ring := PackedVector3Array()
		for q in s["ring"]:
			ring.append(Vector3(float(q[0]), float(s["elevation_m"]), float(q[1])))
		sidewalks.append({"id": s["id"], "ring": ring, "width": float(s["width_m"]),
			"elev": float(s["elevation_m"])})
	parcels = d["parcels"]
	blocks = d["blocks"]


func _build_connectors() -> void:
	for jid in junctions:
		var j: Dictionary = junctions[jid]
		for apid in j["approaches"]:
			var ap: Dictionary = approaches[apid]
			var t_in: Vector3 = ap["fwd"]
			# outgoing lanes leaving this junction, grouped by edge
			var outs := {}
			for eid in edges:
				if eid == ap["edge"]:
					continue
				var e: Dictionary = edges[eid]
				var dir_out := ""
				if e["a"] == jid:
					dir_out = "ab"
				elif e["b"] == jid:
					dir_out = "ba"
				else:
					continue
				var t_out: Vector3 = e["dir"] if dir_out == "ab" else -e["dir"]
				var lanes: Array = []
				for ln in e["lanes"]:
					if ln["dir"] == dir_out:
						lanes.append(ln["id"])
				outs[eid] = {"t": t_out, "lanes": lanes}
			for lid in ap["lanes"]:
				var lane: Seg = segs[lid]
				var made := 0
				for pass_i in range(2):
					if pass_i == 1 and made > 0:
						break
					for eid in outs:
						var o: Dictionary = outs[eid]
						var cy: float = t_in.z * o["t"].x - t_in.x * o["t"].z
						var dt: float = t_in.dot(o["t"])
						var turn := "straight"
						if cy < -0.5:
							turn = "right"
						elif cy > 0.5:
							turn = "left"
						if turn == "straight" and dt < 0.0:
							continue
						if pass_i == 0:
							if turn == "left" and lane.index != 0:
								continue
							if turn == "right" and lane.index != o["lanes"].size() - 1:
								continue
						if lane.index >= o["lanes"].size():
							continue
						var target_id: String = o["lanes"][lane.index]
						var target: Seg = segs[target_id]
						var c := Seg.new()
						c.id = "%s>%s" % [lid, target_id]
						c.kind = "conn"
						c.turn = turn
						c.junction = jid
						c.index = lane.index
						c.speed_mps = lane.speed_mps
						c.pts = _bezier(lane.pts[lane.pts.size() - 1], t_in, target.pts[0], o["t"])
						c.finalize()
						c.vmax = _curv_speed(c)
						c.next = [target_id]
						segs[c.id] = c
						lane.next.append(c.id)
						made += 1


static func _bezier(p0: Vector3, t0: Vector3, p3: Vector3, t3: Vector3) -> PackedVector3Array:
	var h := 0.0
	var dist := p0.distance_to(p3)
	if absf(t0.dot(t3)) > 0.95:
		h = dist / 3.0
	else:
		# corner point where the two lane lines meet
		var denom := t0.x * t3.z - t0.z * t3.x
		var dp := p3 - p0
		var u := (dp.x * t3.z - dp.z * t3.x) / denom
		var corner := p0 + t0 * u
		h = 0.5523 * 0.5 * (p0.distance_to(corner) + p3.distance_to(corner))
	var p1 := p0 + t0 * h
	var p2 := p3 - t3 * h
	var out := PackedVector3Array()
	var n := 12
	for i in range(n + 1):
		var u2 := float(i) / n
		var a := p0.lerp(p1, u2)
		var b := p1.lerp(p2, u2)
		var c := p2.lerp(p3, u2)
		out.append(a.lerp(b, u2).lerp(b.lerp(c, u2), u2))
	return out


static func _curv_speed(c: Seg) -> float:
	var kmax := 0.0
	for i in range(1, c.pts.size() - 1):
		var a := c.pts[i - 1]
		var b := c.pts[i]
		var d := c.pts[i + 1]
		var t1 := (b - a).normalized()
		var t2 := (d - b).normalized()
		var ang := acos(clampf(t1.dot(t2), -1.0, 1.0))
		var ds := 0.5 * (a.distance_to(b) + b.distance_to(d))
		kmax = maxf(kmax, ang / maxf(ds, 1e-3))
	if kmax < 1e-4:
		return c.speed_mps
	return minf(c.speed_mps, sqrt(2.6 / kmax))


## Nearest lane (kind "lane") to p: returns {lane, s, lat, dist} or {} when none within max_d.
func nearest_lane(p: Vector3, max_d: float = 1e9, kinds := ["lane"]) -> Dictionary:
	var best := {}
	var best_d := max_d
	for id in segs:
		var sg: Seg = segs[id]
		if not kinds.has(sg.kind):
			continue
		var pr := sg.project(p)
		var s := clampf(pr.x, 0.0, sg.length)
		var q := sg.point_at(s)
		var d := Vector2(p.x - q.x, p.z - q.z).length()
		if d < best_d:
			best_d = d
			best = {"lane": id, "s": s, "lat": pr.y, "dist": d}
	return best


## A* over segments from (from_id) to (to_id). Returns the list of ids, from first.
func route(from_id: String, to_id: String) -> Array:
	if from_id == to_id:
		return [from_id]
	var goal: Vector3 = segs[to_id].pts[0]
	var open := {from_id: 0.0}
	var g := {from_id: 0.0}
	var came := {}
	var closed := {}
	while not open.is_empty():
		var cur := ""
		var cur_f := INF
		for k in open:
			if open[k] < cur_f:
				cur_f = open[k]
				cur = k
		open.erase(cur)
		if cur == to_id:
			var out: Array = [cur]
			while came.has(cur):
				cur = came[cur]
				out.push_front(cur)
			return out
		closed[cur] = true
		var sg: Seg = segs[cur]
		for nx in sg.next:
			if closed.has(nx):
				continue
			var ng: float = g[cur] + sg.length
			if not g.has(nx) or ng < g[nx]:
				g[nx] = ng
				came[nx] = cur
				var h: float = segs[nx].pts[0].distance_to(goal)
				open[nx] = ng + h
	return []


func signalised_approaches_near(p: Vector3, r: float) -> Array:
	var out: Array = []
	for id in approaches:
		var ap: Dictionary = approaches[id]
		if not ap["signalised"]:
			continue
		if Vector2(p.x - ap["stop_p"].x, p.z - ap["stop_p"].z).length() < r:
			out.append(ap)
	return out


func sidewalk_point(sw: Dictionary, s: float) -> Dictionary:
	var ring: PackedVector3Array = sw["ring"]
	var total := 0.0
	var n := ring.size()
	for i in range(n):
		total += ring[i].distance_to(ring[(i + 1) % n])
	s = fposmod(s, total)
	var acc := 0.0
	for i in range(n):
		var a := ring[i]
		var b := ring[(i + 1) % n]
		var l := a.distance_to(b)
		if s <= acc + l:
			var u := (s - acc) / l
			return {"pos": a.lerp(b, u), "fwd": (b - a).normalized(), "i": i}
		acc += l
	return {"pos": ring[0], "fwd": (ring[1] - ring[0]).normalized(), "i": 0}


## Resolves an anchor ("at") into {pos, fwd} or {} if unknown.
func resolve(at, player_pos := Vector3.ZERO) -> Dictionary:
	if at is Array and at.size() == 3:
		return {"pos": _v3(at), "fwd": Vector3(0, 0, -1)}
	if at is String:
		if at == "player":
			return {"pos": player_pos, "fwd": Vector3(0, 0, -1)}
		if pois.has(at):
			return {"pos": pois[at]["pos"], "fwd": Vector3(0, 0, -1)}
		return {}
	if not (at is Dictionary):
		return {}
	if at.has("lane"):
		var sg: Seg = segs.get(at["lane"])
		if sg == null:
			return {}
		var s := float(at.get("s", 0.0))
		return {"pos": sg.point_at(s), "fwd": sg.tangent_at(s), "lane": sg.id, "s": s}
	if at.has("intersection") and at.has("approach"):
		var apid := _approach_id(at["intersection"], at["approach"])
		if apid == "":
			return {}
		var ap: Dictionary = approaches[apid]
		var k := int(at.get("lane_index", ap["lanes"].size() - 1))
		var sg2: Seg = segs[ap["lanes"][k]]
		var s2 := sg2.length - float(at.get("before_m", 30.0))
		return {"pos": sg2.point_at(s2), "fwd": sg2.tangent_at(s2), "lane": sg2.id, "s": s2}
	if at.has("corner_of"):
		var apid2 := _approach_id(at["corner_of"], at.get("approach", 0))
		if apid2 == "":
			return {}
		var ap2: Dictionary = approaches[apid2]
		var pos: Vector3 = ap2["stop_p"] + ap2["right"] * (ap2["half_w"] + 1.5)
		pos.y = 0.15
		return {"pos": pos, "fwd": ap2["fwd"]}
	if at.has("sidewalk"):
		for sw in sidewalks:
			if sw["id"] == at["sidewalk"]:
				return sidewalk_point(sw, float(at.get("s", 0.0)))
		return {}
	if at.has("poi"):
		var poi = pois.get(at["poi"])
		if poi == null:
			return {}
		var pos2: Vector3 = poi["pos"]
		if at.has("offset"):
			pos2 += _v3(at["offset"])
		return {"pos": pos2, "fwd": Vector3(0, 0, -1)}
	return {}


func _approach_id(junction_id, approach) -> String:
	if not junctions.has(junction_id):
		return ""
	var list: Array = junctions[junction_id]["approaches"]
	if approach is String:
		return approach if approaches.has(approach) else ""
	var k := int(approach)
	if k < 0 or k >= list.size():
		return ""
	return list[k]
