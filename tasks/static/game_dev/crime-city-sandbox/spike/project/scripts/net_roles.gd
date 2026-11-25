class_name NetRoles
extends Node
## Spike network roles (items 5 and 6). Packet level, no RPCs:
##  server  - simulates the block (cars, people), one avatar per client, snapshots at 20 Hz
##  client  - builds the static world, shows interpolated replicas, sends wander input at 30 Hz
##  nettest - one process hosting a server peer and N client peers (ENet or WebSocket) that
##            exchange stamped packets through the external proxy; prints delivery statistics
## All processes run on one machine, so they share the system clock for latency figures.

const SNAP_HZ := 20.0
const INPUT_HZ := 30.0
const INTERP_S := 0.1

var role := ""
var game: Node
var peer: MultiplayerPeer
var t_acc := 0.0
var log_file: FileAccess
var log_ids: Array = []
var log_t := 0.0
var avatars := {}            # server: peer id -> Person
var replicas := {}           # client: entity id -> {node, kind, snaps: [[t, pos, yaw, anim]]}
var bytes_sent := {}         # server: peer id -> bytes this second
var bytes_hist: Array = []
var tick_ms: Array = []
var _last_us := 0
var rng := RandomNumberGenerator.new()
var wish := Vector2.ZERO
var wish_t := 0.0
var synced := false
var name_arg := ""
# nettest
var nt_server: MultiplayerPeer
var nt_clients: Array = []
var nt_stats := {}
var nt_seq := 0
var nt_t0 := 0.0
var nt_seconds := 30.0
var nt_transport := "enet"


static func start(p_role: String, g: Node) -> void:
	var n := NetRoles.new()
	n.name = "Net"
	n.role = p_role
	n.game = g
	g.main.add_child(n)
	n._begin()


func _ready() -> void:
	process_physics_priority = -40


func _now() -> float:
	return Time.get_unix_time_from_system()


func _begin() -> void:
	var a: Dictionary = game.args
	name_arg = a.get("name", "c")
	rng.seed = hash(name_arg)
	if a.has("log"):
		log_file = FileAccess.open(a["log"], FileAccess.WRITE)
	match role:
		"server":
			game.world_reset({"seed": game.seed_value, "density": float(a.get("density", "1.0"))})
			var e := ENetMultiplayerPeer.new()
			var err := e.create_server(int(a.get("port", "24600")), int(a.get("max-players", "16")))
			if err != OK:
				printerr("NET server create failed ", err)
				get_tree().quit(2)
				return
			peer = e
			peer.peer_connected.connect(_on_peer_connected)
			peer.peer_disconnected.connect(_on_peer_disconnected)
			for i in range(10):
				log_ids.append(i + 2)
			print("NET_READY server port=", a.get("port", "24600"))
		"client":
			# static world only; the dynamic world comes from snapshots
			for c in game.dyn_root.get_children():
				game.despawn(c)
			game.traffic.set_physics_process(false)
			game.wanted.set_physics_process(false)
			game.player = null
			var hp: PackedStringArray = String(a.get("connect", "127.0.0.1:24600")).split(":")
			var e2 := ENetMultiplayerPeer.new()
			var err2 := e2.create_client(hp[0], int(hp[1]))
			if err2 != OK:
				printerr("NET client create failed ", err2)
				get_tree().quit(2)
				return
			peer = e2
			for i in range(10):
				log_ids.append(i + 2)
			print("NET_CLIENT connecting ", a.get("connect", ""))
		"nettest":
			_nettest_begin(a)


# ---------------------------------------------------------------- server

func _on_peer_connected(id: int) -> void:
	var home: Dictionary = game.plan.pois.get("safehouse_a", {})
	var p: Person = game.make_person("online_player", "player", game.LEADS["lead_c"], home.get("pos", Vector3.ZERO))
	p.behaviour = "remote"
	avatars[id] = p
	bytes_sent[id] = 0
	print("NET peer connected ", id, " total=", avatars.size())


func _on_peer_disconnected(id: int) -> void:
	if avatars.has(id):
		game.despawn(avatars[id])
		avatars.erase(id)
	print("NET peer left ", id)


func _server_tick(dt: float) -> void:
	while peer.get_available_packet_count() > 0:
		var from := peer.get_packet_peer()
		var pkt := peer.get_packet()
		if pkt.size() >= 9 and pkt[0] == 1 and avatars.has(from):
			var dx := pkt.decode_float(1)
			var dz := pkt.decode_float(5)
			var av: Person = avatars[from]
			av.desired = Vector3(dx, 0.0, dz).limit_length(1.0) * 4.2
	t_acc += dt
	if t_acc >= 1.0 / SNAP_HZ:
		t_acc -= 1.0 / SNAP_HZ
		var snap := _snapshot()
		peer.set_transfer_mode(MultiplayerPeer.TRANSFER_MODE_UNRELIABLE)
		peer.set_target_peer(0)
		peer.put_packet(snap)
		for id in bytes_sent:
			bytes_sent[id] += snap.size()
	log_t += dt
	if log_t >= 0.25:
		log_t -= 0.25
		_log_positions(_entity_positions())


func _entity_positions() -> Dictionary:
	var out := {}
	for e in get_tree().get_nodes_in_group("entity"):
		var k: String = e.get_meta("kind", "")
		if k == "npc" or k == "vehicle" or k == "player":
			out[int(e.get_meta("entity_id"))] = [e.global_position, e.global_basis.get_euler().y,
				(e.cur_clip if e is Person else "")]
	return out


func _snapshot() -> PackedByteArray:
	var ents := _entity_positions()
	var buf := PackedByteArray()
	buf.resize(13 + ents.size() * 22)
	buf.encode_u8(0, 2)
	buf.encode_double(1, _now())
	buf.encode_u32(9, ents.size())
	var o := 13
	var clip_code := {"": 0, "idle": 1, "walk": 2, "run": 3, "sprint": 4, "sit": 5}
	for id in ents:
		var v: Array = ents[id]
		var p: Vector3 = v[0]
		buf.encode_u32(o, id)
		buf.encode_float(o + 4, p.x)
		buf.encode_float(o + 8, p.y)
		buf.encode_float(o + 12, p.z)
		buf.encode_float(o + 16, v[1])
		buf.encode_u8(o + 20, clip_code.get(v[2], 0))
		buf.encode_u8(o + 21, 1 if v[2] == "" else 2)
		o += 22
	return buf


# ---------------------------------------------------------------- client

func _client_tick(dt: float) -> void:
	while peer.get_available_packet_count() > 0:
		var pkt := peer.get_packet()
		if pkt.size() >= 13 and pkt[0] == 2:
			_apply_snapshot(pkt)
	# wander input
	wish_t -= dt
	if wish_t <= 0.0:
		wish_t = rng.randf_range(1.0, 3.0)
		var ang := rng.randf_range(-PI, PI)
		wish = Vector2(cos(ang), sin(ang)) * rng.randf_range(0.0, 1.0)
	t_acc += dt
	if t_acc >= 1.0 / INPUT_HZ and peer.get_connection_status() == MultiplayerPeer.CONNECTION_CONNECTED:
		t_acc -= 1.0 / INPUT_HZ
		var b := PackedByteArray()
		b.resize(9)
		b.encode_u8(0, 1)
		b.encode_float(1, wish.x)
		b.encode_float(5, wish.y)
		peer.set_transfer_mode(MultiplayerPeer.TRANSFER_MODE_UNRELIABLE_ORDERED)
		peer.set_target_peer(1)
		peer.put_packet(b)
	# interpolate replicas at now - INTERP_S
	var rt := _now() - INTERP_S
	var shown := {}
	for id in replicas:
		var r: Dictionary = replicas[id]
		var snaps: Array = r["snaps"]
		if snaps.is_empty():
			continue
		var pos: Vector3 = snaps[snaps.size() - 1][1]
		var yaw: float = snaps[snaps.size() - 1][2]
		for i in range(snaps.size() - 1):
			if snaps[i][0] <= rt and rt <= snaps[i + 1][0]:
				var u: float = (rt - snaps[i][0]) / maxf(snaps[i + 1][0] - snaps[i][0], 1e-6)
				pos = snaps[i][1].lerp(snaps[i + 1][1], u)
				yaw = lerp_angle(snaps[i][2], snaps[i + 1][2], u)
				break
		var n: Node3D = r["node"]
		n.global_position = pos
		n.rotation.y = yaw
		shown[id] = [pos, yaw, ""]
		if r.has("anim"):
			var want: String = ["idle", "idle", "walk", "run", "sprint", "sit"][snaps[snaps.size() - 1][3]]
			if r["clip"] != want:
				r["clip"] = want
				r["anim"].play(r["names"].get(want, want), 0.15)
	log_t += dt
	if log_t >= 0.25:
		log_t -= 0.25
		_log_positions(shown)


func _apply_snapshot(pkt: PackedByteArray) -> void:
	var ts := pkt.decode_double(1)
	var n := pkt.decode_u32(9)
	var o := 13
	for i in range(n):
		var id := pkt.decode_u32(o)
		var p := Vector3(pkt.decode_float(o + 4), pkt.decode_float(o + 8), pkt.decode_float(o + 12))
		var yaw := pkt.decode_float(o + 16)
		var clip := pkt.decode_u8(o + 20)
		var kind := pkt.decode_u8(o + 21)
		o += 22
		if not replicas.has(id):
			replicas[id] = _make_replica(id, kind)
		var snaps: Array = replicas[id]["snaps"]
		if snaps.is_empty() or ts > snaps[snaps.size() - 1][0]:
			snaps.append([ts, p, yaw, clip])
			if snaps.size() > 12:
				snaps.pop_front()
	if not synced:
		synced = true
		print("NET_CLIENT synced entities=", n)


func _make_replica(id: int, kind: int) -> Dictionary:
	var r := {"snaps": [], "clip": ""}
	if kind == 1:
		var holder := Node3D.new()
		holder.name = "R%d" % id
		CarVisual.attach(holder, "sedan", "raycast")
		game.dyn_root.add_child(holder)
		r["node"] = holder
	else:
		var holder2 := Node3D.new()
		holder2.name = "R%d" % id
		var vis: Node3D
		var names := {}
		if game.art == "ubc" and RealArt.available():
			vis = RealArt.build_visual({})
			names = RealArt.CLIP_NAMES
		else:
			vis = Humanoid.build_visual(game.LEADS["lead_b"])
		vis.rotation.y = PI
		holder2.add_child(vis)
		game.dyn_root.add_child(holder2)
		r["node"] = holder2
		r["anim"] = vis.get_node("Anim")
		r["names"] = names
	return r


func _log_positions(d: Dictionary) -> void:
	if log_file == null:
		return
	var rec := {"t": _now(), "p": {}}
	for id in log_ids:
		if d.has(id):
			var p: Vector3 = d[id][0]
			rec["p"][str(id)] = [snappedf(p.x, 0.001), snappedf(p.z, 0.001)]
	log_file.store_line(JSON.stringify(rec))
	log_file.flush()


# ---------------------------------------------------------------- shared tick

func _physics_process(dt: float) -> void:
	var now := Time.get_ticks_usec()
	if _last_us > 0:
		tick_ms.append((now - _last_us) / 1000.0)
	_last_us = now
	if peer != null:
		peer.poll()
	match role:
		"server":
			_server_tick(dt)
			_report_server(dt)
		"client":
			_client_tick(dt)
		"nettest":
			_nettest_tick()


var _rep_t := 0.0
func _report_server(dt: float) -> void:
	_rep_t += dt
	if _rep_t < 5.0:
		return
	_rep_t = 0.0
	var arr := tick_ms.duplicate()
	arr.sort()
	var bw := {}
	for id in bytes_sent:
		bw[str(id)] = bytes_sent[id] / 5.0
		bytes_sent[id] = 0
	var proc: Array = []
	print("NET_STATS ", JSON.stringify({"peers": avatars.size(), "tick_ms_p50": arr[arr.size() / 2] if arr.size() > 0 else 0,
		"tick_ms_p95": arr[int(arr.size() * 0.95)] if arr.size() > 0 else 0, "bytes_per_s": bw,
		"entities": get_tree().get_nodes_in_group("entity").size()}))
	tick_ms.clear()


# ---------------------------------------------------------------- nettest

func _nettest_begin(a: Dictionary) -> void:
	nt_transport = a.get("transport", "enet")
	nt_seconds = float(a.get("seconds", "30"))
	var sport := int(a.get("port", "24700"))
	var cports: PackedStringArray = String(a.get("client-ports", "24701,24702")).split(",")
	nt_server = _make_peer(true, sport, "")
	for i in range(cports.size()):
		var c := _make_peer(false, int(cports[i]), "127.0.0.1")
		nt_clients.append({"peer": c, "index": i, "id": 0, "down": [], "sent_up": 0})
	nt_stats = {"up": {}, "sent_down": {}}
	nt_t0 = _now()
	print("NETTEST_READY transport=", nt_transport)


func _make_peer(server: bool, port: int, host: String) -> MultiplayerPeer:
	if nt_transport == "ws":
		var w := WebSocketMultiplayerPeer.new()
		if server:
			w.create_server(port)
		else:
			w.create_client("ws://%s:%d" % [host, port])
		return w
	var e := ENetMultiplayerPeer.new()
	if server:
		e.create_server(port, 8)
	else:
		e.create_client(host, port)
	return e


var _nt_acc := 0.0
var _nt_prev := 0.0
var _nt_hello := {}
func _nettest_tick() -> void:
	nt_server.poll()
	for c in nt_clients:
		c["peer"].poll()
	var now := _now()
	var el := now - nt_t0
	# server receives
	while nt_server.get_available_packet_count() > 0:
		var from := nt_server.get_packet_peer()
		var pkt := nt_server.get_packet()
		if pkt.size() >= 14:
			var ci := pkt.decode_u8(1)
			if not _nt_hello.has(from) and game.args.get("throttle", "") == "off" and nt_server is ENetMultiplayerPeer:
				# keep ENet from dropping unreliable packets after loss (packet throttle fixed at full)
				(nt_server as ENetMultiplayerPeer).get_peer(from).throttle_configure(5000, 0, 0)
			if not _nt_hello.has(from) and game.args.has("enet-timeout-min") and nt_server is ENetMultiplayerPeer:
				(nt_server as ENetMultiplayerPeer).get_peer(from).set_timeout(32, int(game.args["enet-timeout-min"]), 30000)
			_nt_hello[from] = ci
			var key := str(ci)
			if not nt_stats["up"].has(key):
				nt_stats["up"][key] = []
			nt_stats["up"][key].append([now, pkt.decode_u32(2), now - pkt.decode_double(6)])
	# clients receive
	for c in nt_clients:
		var p: MultiplayerPeer = c["peer"]
		while p.get_available_packet_count() > 0:
			var pkt2 := p.get_packet()
			if pkt2.size() >= 14:
				c["down"].append([now, pkt2.decode_u32(2), now - pkt2.decode_double(6)])
	if _nt_prev == 0.0:
		_nt_prev = now
	_nt_acc += now - _nt_prev
	_nt_prev = now
	if _nt_acc >= 1.0 / 30.0:
		_nt_acc -= 1.0 / 30.0
		nt_seq += 1
		# downstream: 600-byte stamped packet to each known client peer
		for from_id in _nt_hello:
			var b := PackedByteArray()
			b.resize(600)
			b.encode_u8(0, 3)
			b.encode_u8(1, _nt_hello[from_id])
			b.encode_u32(2, nt_seq)
			b.encode_double(6, _now())
			nt_server.set_transfer_mode(MultiplayerPeer.TRANSFER_MODE_UNRELIABLE)
			nt_server.set_target_peer(from_id)
			nt_server.put_packet(b)
			var key2 := str(_nt_hello[from_id])
			nt_stats["sent_down"][key2] = nt_stats["sent_down"].get(key2, 0) + 1
		for c in nt_clients:
			var p2: MultiplayerPeer = c["peer"]
			if p2.get_connection_status() != MultiplayerPeer.CONNECTION_CONNECTED:
				continue
			if not c.has("throttled") and game.args.get("throttle", "") == "off" and p2 is ENetMultiplayerPeer:
				(p2 as ENetMultiplayerPeer).get_peer(1).throttle_configure(5000, 0, 0)
				c["throttled"] = true
			if not c.has("timeout_set") and game.args.has("enet-timeout-min") and p2 is ENetMultiplayerPeer:
				(p2 as ENetMultiplayerPeer).get_peer(1).set_timeout(32, int(game.args["enet-timeout-min"]), 30000)
				c["timeout_set"] = true
			var b2 := PackedByteArray()
			b2.resize(60)
			b2.encode_u8(0, 4)
			b2.encode_u8(1, c["index"])
			b2.encode_u32(2, nt_seq)
			b2.encode_double(6, _now())
			p2.set_transfer_mode(MultiplayerPeer.TRANSFER_MODE_UNRELIABLE)
			p2.set_target_peer(1)
			p2.put_packet(b2)
			c["sent_up"] += 1
	if el >= nt_seconds:
		_nettest_report()
		get_tree().quit(0)


func _nettest_report() -> void:
	var out := {"transport": nt_transport, "seconds": nt_seconds, "t0": nt_t0, "clients": []}
	for c in nt_clients:
		var key := str(c["index"])
		out["clients"].append({"index": c["index"], "down": _nt_summary(c["down"], nt_stats["sent_down"].get(key, 0)),
			"up": _nt_summary(nt_stats["up"].get(key, []), c["sent_up"]),
			"down_raw": c["down"].map(func(x): return [snappedf(x[0] - nt_t0, 0.001), x[1], snappedf(x[2] * 1000.0, 0.01)])})
	print("NETTEST_RESULT ", JSON.stringify(out))


func _nt_summary(recs: Array, sent: int) -> Dictionary:
	var seqs := {}
	var dup := 0
	var reorder := 0
	var max_seq := -1
	var lat: Array = []
	var gaps: Array = []
	var prev_t := -1.0
	for r in recs:
		var s: int = r[1]
		if seqs.has(s):
			dup += 1
		seqs[s] = true
		if s < max_seq:
			reorder += 1
		max_seq = maxi(max_seq, s)
		lat.append(r[2] * 1000.0)
		if prev_t > 0.0:
			gaps.append((r[0] - prev_t) * 1000.0)
		prev_t = r[0]
	lat.sort()
	gaps.sort()
	return {"sent": sent, "received": recs.size(), "unique": seqs.size(), "dup": dup, "reordered": reorder,
		"delivered_frac": float(seqs.size()) / maxf(sent, 1.0),
		"lat_ms_p50": lat[lat.size() / 2] if lat.size() > 0 else null,
		"lat_ms_p95": lat[int(lat.size() * 0.95)] if lat.size() > 0 else null,
		"lat_ms_max": lat[lat.size() - 1] if lat.size() > 0 else null,
		"max_gap_ms": gaps[gaps.size() - 1] if gaps.size() > 0 else null}
