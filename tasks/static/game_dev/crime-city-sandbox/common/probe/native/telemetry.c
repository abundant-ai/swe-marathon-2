// QA telemetry node, native core (plain C against the engine's dumped extension
// interface; no godot-cpp).
//
// The QA kit copies this library into a copy of the game, next to a scene whose root
// node is the class registered here, and lists that scene first among the project's
// autoloads. The class name is the library's file name, chosen at random per copy.
//
// At engine start-up (scene initialisation level, before any game script runs) the
// library reads the link settings from the environment, wipes them from it, and
// connects to the kit over 127.0.0.1:
//   QA_TELEMETRY_PORT   TCP port of the kit
//   QA_TELEMETRY_KEY    per-run key, 64 hex digits; never visible to game scripts
//   QA_TELEMETRY_MODE   "lockstep" (default) or "realtime"
// Without them the node does nothing, so a prepared copy still runs on its own.
//
// Every physics tick, before the game's own nodes (lowest priority, internal physics
// processing, process mode "always"):
//   lockstep: at an observation tick the node sends a frame and blocks until the
//     kit's next command; the command says how many ticks to run, which input actions
//     to press at which tick of the run, which DevConsole commands to execute, what to
//     observe and which queries to answer. Inputs are injected before the game's tick
//     and flushed, so an action injected at tick t acts in tick t.
//   realtime: the node never blocks. It applies the commands that have arrived, sends
//     a heartbeat (tick, monotonic microseconds) every tick and a frame every `every`
//     ticks.
// Messages in both directions: 4-byte big-endian length L, a 32-byte HMAC-SHA256 tag
// of the payload under the per-run key, then L - 32 bytes of UTF-8 JSON carrying a
// sequence number "n". A bad tag, a wrong sequence number or an oversized message
// stops the game with exit code 3; losing the link stops it with exit code 4. If the
// node leaves the scene tree it sends a final "gone" message and stops.
#include <arpa/inet.h>
#include <dlfcn.h>
#include <errno.h>
#include <math.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <poll.h>
#include <pthread.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <time.h>
#include <unistd.h>

#include "gen/binds.h"
#include "gen/gdextension_interface.h"
#include "jw.h"
#include "sha256.h"

#define EXPORT __attribute__((visibility("default")))
#define FRAME_LIMIT ((size_t)64 << 20)
#define EVENT_LIMIT ((size_t)1 << 20)
#define EVENTS_LIMIT ((size_t)16 << 20)
#define DEV_LIMIT ((size_t)16 << 20)
#define INBOUND_LIMIT ((uint32_t)16 << 20)
#define MAX_DEPTH 24
#define MAX_KEYS 32
#define MAX_BONE_IDS 64
#define MAX_BONE_NAMES 96
#define MAX_SEAT_IDS 64                // vehicles whose seats a frame lists
#define MAX_SHOWN (MAX_BONE_IDS + 16)  // skeletons followed for the pose they show
#define MAX_SHOWN_BONES 256            // bones kept per followed skeleton
#define EXIT_BAD_LINK 3
#define EXIT_LOST_LINK 4

typedef struct { uint64_t w; } SN;     // StringName storage
typedef struct { uint64_t w; } GS;     // String storage
typedef struct { uint64_t w; } GA;     // Array storage
typedef struct { uint64_t w[3]; } Var; // Variant storage (24 bytes, single precision build)
typedef struct { float x, y, z; } V3;
typedef struct { float r[3][3]; float o[3]; } Xf; // Transform3D: basis rows, then origin
typedef GDExtensionObjectPtr Obj;

_Static_assert(sizeof(Var) == 24, "Variant size");
_Static_assert(sizeof(Xf) == 48, "Transform3D size");

enum {
	T_NIL = GDEXTENSION_VARIANT_TYPE_NIL,
	T_BOOL = GDEXTENSION_VARIANT_TYPE_BOOL,
	T_INT = GDEXTENSION_VARIANT_TYPE_INT,
	T_FLOAT = GDEXTENSION_VARIANT_TYPE_FLOAT,
	T_STRING = GDEXTENSION_VARIANT_TYPE_STRING,
	T_V2 = GDEXTENSION_VARIANT_TYPE_VECTOR2,
	T_V2I = GDEXTENSION_VARIANT_TYPE_VECTOR2I,
	T_V3 = GDEXTENSION_VARIANT_TYPE_VECTOR3,
	T_V3I = GDEXTENSION_VARIANT_TYPE_VECTOR3I,
	T_V4 = GDEXTENSION_VARIANT_TYPE_VECTOR4,
	T_V4I = GDEXTENSION_VARIANT_TYPE_VECTOR4I,
	T_QUAT = GDEXTENSION_VARIANT_TYPE_QUATERNION,
	T_COLOR = GDEXTENSION_VARIANT_TYPE_COLOR,
	T_SNAME = GDEXTENSION_VARIANT_TYPE_STRING_NAME,
	T_NPATH = GDEXTENSION_VARIANT_TYPE_NODE_PATH,
	T_OBJECT = GDEXTENSION_VARIANT_TYPE_OBJECT,
	T_CALLABLE = GDEXTENSION_VARIANT_TYPE_CALLABLE,
	T_DICT = GDEXTENSION_VARIANT_TYPE_DICTIONARY,
	T_ARRAY = GDEXTENSION_VARIANT_TYPE_ARRAY,
	T_PACKED_FIRST = GDEXTENSION_VARIANT_TYPE_PACKED_BYTE_ARRAY,
	T_PACKED_LAST = GDEXTENSION_VARIANT_TYPE_PACKED_VECTOR4_ARRAY,
	T_MAX = GDEXTENSION_VARIANT_TYPE_VARIANT_MAX,
};

// ------------------------------------------------------------------ engine interface
static GDExtensionClassLibraryPtr g_lib;
static GDExtensionInterfaceStringNameNewWithLatin1Chars f_sn_new;
static GDExtensionInterfaceStringNewWithUtf8CharsAndLen2 f_str_new;
static GDExtensionInterfaceStringToUtf8Chars f_str_utf8;
static GDExtensionInterfaceVariantNewNil f_v_nil;
static GDExtensionInterfaceVariantNewCopy f_v_copy;
static GDExtensionInterfaceVariantDestroy f_v_destroy;
static GDExtensionInterfaceVariantGetType f_v_type;
static GDExtensionInterfaceVariantCall f_v_call;
static GDExtensionInterfaceVariantGet f_v_get;
static GDExtensionInterfaceVariantGetIndexed f_v_get_indexed;
static GDExtensionInterfaceVariantStringify f_v_stringify;
static GDExtensionInterfaceVariantConstruct f_v_construct;
static GDExtensionInterfaceVariantGetObjectInstanceId f_v_obj_id;
static GDExtensionInterfaceGetVariantFromTypeConstructor f_from_type;
static GDExtensionInterfaceGetVariantToTypeConstructor f_to_type;
static GDExtensionInterfaceVariantGetPtrConstructor f_ctor;
static GDExtensionInterfaceVariantGetPtrDestructor f_dtor;
static GDExtensionInterfaceVariantGetPtrBuiltinMethod f_builtin;
static GDExtensionInterfaceArrayOperatorIndexConst f_arr_at;
static GDExtensionInterfaceObjectMethodBindPtrcall f_ptrcall;
static GDExtensionInterfaceClassdbGetMethodBind f_get_mb;
static GDExtensionInterfaceClassdbConstructObject3 f_construct;
static GDExtensionInterfaceClassdbRegisterExtensionClass6 f_reg_class;
static GDExtensionInterfaceObjectSetInstance f_set_instance;
static GDExtensionInterfaceObjectGetInstanceId f_instance_id;
static GDExtensionInterfaceObjectGetInstanceFromId f_from_id;
static GDExtensionInterfaceGlobalGetSingleton f_singleton;
static GDExtensionInterfaceCallableCustomCreate2 f_callable_new;

static GDExtensionVariantFromTypeConstructorFunc vfrom[T_MAX];
static GDExtensionTypeFromVariantConstructorFunc vto[T_MAX];
static GDExtensionPtrConstructor ctor_array, ctor_string;
static GDExtensionPtrDestructor dtor_array, dtor_string, dtor_sname, dtor_callable;
static GDExtensionPtrBuiltInMethod bm_array_size;

static GDExtensionMethodBindPtr mb_get_meta, mb_has_meta, mb_is_class, mb_notification;
static GDExtensionMethodBindPtr mb_get_tree, mb_get_index, mb_set_internal_physics, mb_set_physics_priority;
static GDExtensionMethodBindPtr mb_set_process_mode, mb_find_children, mb_get_parent, mb_is_in_group;
static GDExtensionMethodBindPtr mb_get_viewport, mb_nodes_in_group, mb_get_root, mb_quit;
static GDExtensionMethodBindPtr mb_global_transform, mb_find_bone, mb_bone_global_pose, mb_bone_count;
static GDExtensionMethodBindPtr mb_linear_velocity, mb_real_velocity, mb_physics_frames;
static GDExtensionMethodBindPtr mb_camera_3d, mb_in_frustum, mb_parse_json;
static int g_bind_failed;

// ------------------------------------------------------------------ names
static SN g_class_name, sn_node, sn_entity, sn_m_id, sn_m_kind, sn_m_arch, sn_m_faction;
static SN sn_m_surface, sn_m_parcel, sn_node3d, sn_rigid, sn_character, sn_skeleton_cls;
static SN sn_exec, sn_keys, sn_size, sn_get_node_or_null, sn_has_signal, sn_connect, sn_instantiate;
static SN sn_set_action, sn_set_strength, sn_set_pressed, sn_parse_event, sn_flush_events;
static SN sn_find_world, sn_space_state, sn_set_from, sn_set_to, sn_set_mask, sn_intersect_ray;
static SN sn_get, sn_is_visible, sn_get_children, sn_get_fov, sn_get_bone_name, sn_get_skin;
static SN sn_get_skeleton_path, sn_get_mesh, sn_surface_count, sn_surface_arrays, sn_get_path;
static SN sn_get_version_info, sn_get_setting, sn_get_ticks, sn_get_jitter, sn_get_max_steps;
static SN sn_render_method, sn_display_name, sn_cpu_count, sn_get_env, sn_is_instance_valid;
static SN sn_is_connected, sn_disconnect, sn_seat, sn_m_index, sn_m_door, sn_m_wheel;
static SN sn_collision_object, sn_get_class;

static Var k_run, k_inputs, k_dev, k_observe, k_queries, k_quit, k_n, k_census, k_meta, k_view;
static Var k_bones, k_ids, k_names, k_camera, k_hud, k_state, k_every, k_id, k_type, k_from;
static Var k_to, k_mask, k_points, k_y0, k_y1, k_a, k_b, k_a_up, k_b_up, k_entity, k_keys;
static Var k_position, k_collider, k_string, k_ok, k_event, k_text, k_star, k_empty;
static Var k_skeleton_updated, k_seats, k_mass, k_collision_layer, k_collision_mask, k_kinds;

// ------------------------------------------------------------------ state
typedef struct {
	int64_t off;      // tick offset from the command's first tick
	Var action;       // action name (String)
	double strength;  // 0 releases the action
} Input;

typedef struct {
	int census, view, camera, state, every, census_kinds;
	int n_meta, n_bone_ids, n_bone_names, n_hud, n_seat_ids, n_kinds;
	SN meta[MAX_KEYS];
	char *meta_txt[MAX_KEYS];
	SN kinds[MAX_KEYS];         // census_kinds: only entities of these kinds are listed
	char *kind_txt[MAX_KEYS];
	int64_t bone_ids[MAX_BONE_IDS];
	int64_t seat_ids[MAX_SEAT_IDS];
	GS bone_gs[MAX_BONE_NAMES];
	char *bone_txt[MAX_BONE_NAMES];
	SN hud[MAX_KEYS];
	char *hud_txt[MAX_KEYS];
} Observe;

static int g_on;             // the link is up and the node acts
static int g_closing;        // the node asked the engine to quit
static int g_realtime;       // 0: lockstep, 1: realtime
static int g_sock = -1;
static uint8_t g_key[32];
static int64_t g_seq_out, g_seq_in;
static Obj g_node;           // the one active instance of the class
static Obj g_tree;
static Var g_devconsole;     // the game's DevConsole node, once found
static GDObjectInstanceID g_devconsole_id;
static int g_hooked;
static int64_t g_left, g_cmd_tick, g_ticks_seen, g_last_frame_tick;
static uint64_t g_last_frame_us, g_own_us;
static Input *g_inputs;
static int g_n_inputs, g_cap_inputs;
static Observe g_obs;
static Var g_pending_queries;
static jbuf g_frame, g_dev, g_events;
static int64_t g_events_dropped;
static pthread_mutex_t g_events_mu = PTHREAD_MUTEX_INITIALIZER;
static uint8_t *g_in;        // realtime: bytes received and not yet parsed
static size_t g_in_n, g_in_cap;

// ------------------------------------------------------------------ small helpers
static uint64_t now_us(void) {
	struct timespec ts;
	clock_gettime(CLOCK_MONOTONIC, &ts);
	return (uint64_t)ts.tv_sec * 1000000u + (uint64_t)ts.tv_nsec / 1000u;
}

static void sn_static(SN *s, const char *text) { f_sn_new(s, text, 1); }

static void str_from(GS *s, const char *text, size_t n) { f_str_new(s, text, (GDExtensionInt)n); }

static void v_nil(Var *v) { f_v_nil(v); }
static void v_free(Var *v) { f_v_destroy(v); }
static int v_type(const Var *v) { return (int)f_v_type((GDExtensionConstVariantPtr)v); }

static void v_int(Var *v, int64_t x) { vfrom[T_INT](v, &x); }
static void v_float(Var *v, double x) { vfrom[T_FLOAT](v, &x); }
static void v_bool(Var *v, int x) {
	GDExtensionBool b = (GDExtensionBool)(x != 0);
	vfrom[T_BOOL](v, &b);
}
static void v_obj(Var *v, Obj o) { vfrom[T_OBJECT](v, &o); }
static void v_vec3(Var *v, V3 p) { vfrom[T_V3](v, &p); }
static void v_text(Var *v, const char *text) {
	GS s;
	str_from(&s, text, strlen(text));
	vfrom[T_STRING](v, &s);
	dtor_string(&s);
}

// The object held by an Object variant, or NULL (also NULL when it has been freed).
static Obj as_obj(const Var *v) {
	if (v_type(v) != T_OBJECT) return NULL;
	GDObjectInstanceID id = f_v_obj_id((GDExtensionConstVariantPtr)v);
	return id ? f_from_id(id) : NULL;
}

// A number variant as a double (bool counts as 0/1); dflt for any other type.
static double as_num(const Var *v, double dflt) {
	int t = v_type(v);
	if (t == T_INT) {
		int64_t x;
		vto[T_INT](&x, (GDExtensionVariantPtr)v);
		return (double)x;
	}
	if (t == T_FLOAT) {
		double x;
		vto[T_FLOAT](&x, (GDExtensionVariantPtr)v);
		return x;
	}
	if (t == T_BOOL) {
		GDExtensionBool b;
		vto[T_BOOL](&b, (GDExtensionVariantPtr)v);
		return b ? 1.0 : 0.0;
	}
	return dflt;
}

// A whole number variant (an int, or a float without a fraction) as an entity id. Returns 1
// and sets *out when it is one.
static int as_id(const Var *v, int64_t *out) {
	int t = v_type(v);
	if (t == T_INT) {
		vto[T_INT](out, (GDExtensionVariantPtr)v);
		return 1;
	}
	if (t != T_FLOAT) return 0;
	double x = as_num(v, 0);
	if (x != floor(x) || fabs(x) > 9.0e18) return 0;
	*out = (int64_t)x;
	return 1;
}

// UTF-8 text of any variant (its string form); the caller frees the result.
static char *as_text(const Var *v, size_t *len) {
	GS s;
	ctor_string(&s, NULL);
	f_v_stringify((GDExtensionConstVariantPtr)v, &s);
	GDExtensionInt n = f_str_utf8(&s, NULL, 0);
	char *out = malloc((size_t)n + 1);
	if (out) {
		f_str_utf8(&s, out, n);
		out[n] = 0;
	}
	dtor_string(&s);
	if (len) *len = out ? (size_t)n : 0;
	return out;
}

// Call a method by name on a variant. ret is always initialised (nil on failure) and
// must be destroyed by the caller. Returns 1 when the call succeeded.
static int vcall(Var *self, const SN *method, const Var *const *args, int argc, Var *ret) {
	GDExtensionCallError e = {0};
	f_v_call(self, method, (const GDExtensionConstVariantPtr *)args, argc, ret, &e);
	return e.error == GDEXTENSION_CALL_OK;
}

// Call a method on an object with up to three variant arguments; see vcall.
static int ocall(Obj o, const SN *method, const Var *a0, const Var *a1, const Var *a2, Var *ret) {
	Var self;
	v_obj(&self, o);
	const Var *args[3] = {a0, a1, a2};
	int argc = a2 ? 3 : a1 ? 2 : a0 ? 1 : 0;
	int ok = vcall(&self, method, args, argc, ret);
	v_free(&self);
	return ok;
}

// Look up key in a Dictionary variant; out is initialised and must be destroyed.
// Returns 1 when the key exists.
static int dget(const Var *dict, const Var *key, Var *out) {
	GDExtensionBool valid = 0;
	f_v_get((GDExtensionConstVariantPtr)dict, (GDExtensionConstVariantPtr)key, out, &valid);
	if (!valid || v_type(out) == T_NIL) return 0;
	return 1;
}

// Element i of an Array variant; out is initialised and must be destroyed.
static int aget(const Var *arr, int64_t i, Var *out) {
	GDExtensionBool valid = 0, oob = 0;
	f_v_get_indexed((GDExtensionConstVariantPtr)arr, i, out, &valid, &oob);
	return valid && !oob;
}

// Number of elements of an Array (or packed array) variant; 0 for other types.
static int64_t asize(const Var *arr) {
	int t = v_type(arr);
	if (t != T_ARRAY && !(t >= T_PACKED_FIRST && t <= T_PACKED_LAST)) return 0;
	Var r;
	int64_t n = 0;
	if (vcall((Var *)arr, &sn_size, NULL, 0, &r)) n = (int64_t)as_num(&r, 0);
	v_free(&r);
	return n;
}

// A number field of a Dictionary variant, or dflt.
static double dnum(const Var *dict, const Var *key, double dflt) {
	Var v;
	double x = dflt;
	if (dget(dict, key, &v)) x = as_num(&v, dflt);
	v_free(&v);
	return x;
}

// Three numbers from an Array variant ([x, y, z]); missing entries are 0.
static V3 as_vec3(const Var *arr) {
	float c[3] = {0, 0, 0};
	for (int i = 0; i < 3; i++) {
		Var e;
		if (aget(arr, i, &e)) c[i] = (float)as_num(&e, 0);
		v_free(&e);
	}
	V3 p = {c[0], c[1], c[2]};
	return p;
}

static int64_t physics_frames(void) {
	static Obj engine;
	if (!engine) {
		SN n;
		f_sn_new(&n, "Engine", 0);
		engine = f_singleton(&n);
		dtor_sname(&n);
	}
	int64_t t = 0;
	if (engine) f_ptrcall(mb_physics_frames, engine, NULL, &t);
	return t;
}

static Obj singleton(const char *name) {
	SN n;
	f_sn_new(&n, name, 0);
	Obj o = f_singleton(&n);
	dtor_sname(&n);
	return o;
}

// A Callable variant that calls fn(ud, ...) on behalf of the node; out must be destroyed.
// Two such callables with the same fn and ud are equal (connect, is_connected, disconnect).
static void custom_callable(GDExtensionCallableCustomCall fn, void *ud, Var *out) {
	GDExtensionCallableCustomInfo2 info;
	memset(&info, 0, sizeof info);
	info.callable_userdata = ud;
	info.token = g_lib;
	info.object_id = g_node ? f_instance_id(g_node) : 0;
	info.call_func = fn;
	uint64_t cbuf[2];
	f_callable_new(cbuf, &info);
	vfrom[T_CALLABLE](out, cbuf);
	dtor_callable(cbuf);
}

// ------------------------------------------------------------------ ptrcall wrappers
static Var meta(Obj o, const SN *key) {
	Var dflt, ret;
	v_nil(&dflt);
	v_nil(&ret);
	const void *args[2] = {key, &dflt};
	f_ptrcall(mb_get_meta, o, args, &ret);
	v_free(&dflt);
	return ret;
}

static int has_meta(Obj o, const SN *key) {
	GDExtensionBool b = 0;
	const void *args[1] = {key};
	f_ptrcall(mb_has_meta, o, args, &b);
	return b != 0;
}

static int is_class(Obj o, const SN *cls) {
	GDExtensionBool b = 0;
	const void *args[1] = {cls};
	f_ptrcall(mb_is_class, o, args, &b);
	return b != 0;
}

static int in_group(Obj o, const SN *group) {
	GDExtensionBool b = 0;
	const void *args[1] = {group};
	f_ptrcall(mb_is_in_group, o, args, &b);
	return b != 0;
}

static Xf global_xf(Obj o) {
	Xf x;
	memset(&x, 0, sizeof x);
	f_ptrcall(mb_global_transform, o, NULL, &x);
	return x;
}

static V3 xf_apply(const Xf *x, const float p[3]) {
	V3 r;
	r.x = x->r[0][0] * p[0] + x->r[0][1] * p[1] + x->r[0][2] * p[2] + x->o[0];
	r.y = x->r[1][0] * p[0] + x->r[1][1] * p[1] + x->r[1][2] * p[2] + x->o[1];
	r.z = x->r[2][0] * p[0] + x->r[2][1] * p[1] + x->r[2][2] * p[2] + x->o[2];
	return r;
}

// Nodes of a group, as an Array the caller destroys with dtor_array.
static GA group_nodes(const SN *group) {
	GA arr;
	ctor_array(&arr, NULL);
	const void *args[1] = {group};
	if (g_tree) f_ptrcall(mb_nodes_in_group, g_tree, args, &arr);
	return arr;
}

static int64_t garr_size(GA *arr) {
	int64_t n = 0;
	bm_array_size(arr, NULL, &n, 0);
	return n;
}

static Obj garr_obj(GA *arr, int64_t i) {
	const Var *v = (const Var *)f_arr_at(arr, i);
	return v ? as_obj(v) : NULL;
}

// Descendants of node of the given class (recursive, owned or not), as an Array.
static GA find_children(Obj node, const char *cls) {
	GS pattern, type;
	str_from(&pattern, "*", 1);
	str_from(&type, cls, strlen(cls));
	GDExtensionBool recursive = 1, owned = 0;
	const void *args[4] = {&pattern, &type, &recursive, &owned};
	GA arr;
	ctor_array(&arr, NULL);
	f_ptrcall(mb_find_children, node, args, &arr);
	dtor_string(&pattern);
	dtor_string(&type);
	return arr;
}

static Obj entity_by_id(int64_t id) {
	GA arr = group_nodes(&sn_entity);
	Obj found = NULL;
	int64_t n = garr_size(&arr);
	for (int64_t i = 0; i < n && !found; i++) {
		Obj o = garr_obj(&arr, i);
		if (!o) continue;
		Var m = meta(o, &sn_m_id);
		if (v_type(&m) != T_NIL && (int64_t)as_num(&m, -1) == id) found = o;
		v_free(&m);
	}
	dtor_array(&arr);
	return found;
}

static Obj first_skeleton(Obj node) {
	GA arr = find_children(node, "Skeleton3D");
	Obj sk = garr_size(&arr) > 0 ? garr_obj(&arr, 0) : NULL;
	dtor_array(&arr);
	return sk;
}

// ------------------------------------------------------------------ JSON of game values
static void jw_var(jbuf *b, const Var *v, int depth);

static void jw_text_of(jbuf *b, const Var *v) {
	size_t n;
	char *t = as_text(v, &n);
	if (t) jb_str(b, t, n);
	else jb_lit(b, "null");
	free(t);
}

static void jw_dict(jbuf *b, const Var *v, int depth) {
	Var keys;
	if (!vcall((Var *)v, &sn_keys, NULL, 0, &keys)) {
		v_free(&keys);
		jb_lit(b, "{}");
		return;
	}
	int64_t n = asize(&keys);
	jb_raw(b, "{", 1);
	for (int64_t i = 0; i < n && !b->over; i++) {
		Var k, val;
		aget(&keys, i, &k);
		if (i) jb_raw(b, ",", 1);
		jw_text_of(b, &k);
		jb_raw(b, ":", 1);
		if (dget(v, &k, &val)) jw_var(b, &val, depth + 1);
		else jb_lit(b, "null");
		v_free(&val);
		v_free(&k);
	}
	jb_raw(b, "}", 1);
	v_free(&keys);
}

static void jw_array(jbuf *b, const Var *v, int depth) {
	int64_t n = asize(v);
	jb_raw(b, "[", 1);
	for (int64_t i = 0; i < n && !b->over; i++) {
		Var e;
		if (i) jb_raw(b, ",", 1);
		if (aget(v, i, &e)) jw_var(b, &e, depth + 1);
		else jb_lit(b, "null");
		v_free(&e);
	}
	jb_raw(b, "]", 1);
}

static void jw_floats(jbuf *b, const float *f, int n) {
	jb_raw(b, "[", 1);
	for (int i = 0; i < n; i++) {
		if (i) jb_raw(b, ",", 1);
		jb_f64(b, f[i]);
	}
	jb_raw(b, "]", 1);
}

static void jw_ints(jbuf *b, const int32_t *x, int n) {
	jb_raw(b, "[", 1);
	for (int i = 0; i < n; i++) {
		if (i) jb_raw(b, ",", 1);
		jb_i64(b, x[i]);
	}
	jb_raw(b, "]", 1);
}

// Write a game value as JSON. Objects become null; nesting deeper than MAX_DEPTH
// becomes null, so self-referencing containers cannot recurse without end.
static void jw_var(jbuf *b, const Var *v, int depth) {
	if (depth > MAX_DEPTH) {
		jb_lit(b, "null");
		return;
	}
	int t = v_type(v);
	GDExtensionVariantPtr p = (GDExtensionVariantPtr)v;
	switch (t) {
		case T_NIL: jb_lit(b, "null"); return;
		case T_BOOL: jb_bool(b, as_num(v, 0) != 0); return;
		case T_INT: {
			int64_t x;
			vto[T_INT](&x, p);
			jb_i64(b, x);
			return;
		}
		case T_FLOAT: jb_f64(b, as_num(v, 0)); return;
		case T_STRING:
		case T_SNAME:
		case T_NPATH: jw_text_of(b, v); return;
		case T_V2: {
			float f[2];
			vto[T_V2](f, p);
			jw_floats(b, f, 2);
			return;
		}
		case T_V3: {
			float f[3];
			vto[T_V3](f, p);
			jw_floats(b, f, 3);
			return;
		}
		case T_V4:
		case T_QUAT:
		case T_COLOR: {
			float f[4];
			vto[t](f, p);
			jw_floats(b, f, 4);
			return;
		}
		case T_V2I: {
			int32_t x[2];
			vto[T_V2I](x, p);
			jw_ints(b, x, 2);
			return;
		}
		case T_V3I: {
			int32_t x[3];
			vto[T_V3I](x, p);
			jw_ints(b, x, 3);
			return;
		}
		case T_V4I: {
			int32_t x[4];
			vto[T_V4I](x, p);
			jw_ints(b, x, 4);
			return;
		}
		case T_DICT: jw_dict(b, v, depth); return;
		case T_ARRAY: jw_array(b, v, depth); return;
		case T_OBJECT: jb_lit(b, "null"); return;
		default: break;
	}
	if (t >= T_PACKED_FIRST && t <= T_PACKED_LAST) {
		Var arr;
		GDExtensionCallError e = {0};
		const GDExtensionConstVariantPtr args[1] = {v};
		f_v_construct(GDEXTENSION_VARIANT_TYPE_ARRAY, &arr, args, 1, &e);
		if (e.error == GDEXTENSION_CALL_OK) jw_array(b, &arr, depth);
		else jb_lit(b, "[]");
		v_free(&arr);
		return;
	}
	jw_text_of(b, v);
}

// ------------------------------------------------------------------ link
static void stop_game(int code, const char *why) {
	if (g_closing) return;
	g_closing = 1;
	g_on = 0;
	fprintf(stderr, "qa telemetry: stopping (%s)\n", why);
	if (g_sock >= 0) {
		close(g_sock);
		g_sock = -1;
	}
	if (g_tree) {
		int64_t c = code;
		const void *args[1] = {&c};
		f_ptrcall(mb_quit, g_tree, args, NULL);
	} else {
		_exit(code);
	}
}

static int write_all(const uint8_t *p, size_t n) {
	while (n > 0) {
#ifdef MSG_NOSIGNAL
		ssize_t r = send(g_sock, p, n, MSG_NOSIGNAL);
#else
		ssize_t r = send(g_sock, p, n, 0);
#endif
		if (r < 0 && errno == EINTR) continue;
		if (r <= 0) return 0;
		p += r;
		n -= (size_t)r;
	}
	return 1;
}

static int read_all(uint8_t *p, size_t n) {
	while (n > 0) {
		ssize_t r = recv(g_sock, p, n, 0);
		if (r < 0 && errno == EINTR) continue;
		if (r <= 0) return 0;
		p += r;
		n -= (size_t)r;
	}
	return 1;
}

// Sign and send one JSON payload. On failure the game stops (link lost).
static void send_payload(const char *p, size_t n) {
	if (g_sock < 0) return;
	uint8_t hdr[36];
	uint32_t total = (uint32_t)n + 32;
	hdr[0] = (uint8_t)(total >> 24);
	hdr[1] = (uint8_t)(total >> 16);
	hdr[2] = (uint8_t)(total >> 8);
	hdr[3] = (uint8_t)total;
	hmac_sha256(g_key, sizeof g_key, (const uint8_t *)p, n, hdr + 4);
	if (!write_all(hdr, 36) || !write_all((const uint8_t *)p, n)) stop_game(EXIT_LOST_LINK, "link lost");
}

// Close the JSON object in b with the next outbound sequence number and send it.
static void send_frame_buf(jbuf *b) {
	if (b->over) {
		jb_clear(b);
		jb_lit(b, "{\"overflow\":true,\"t\":");
		jb_i64(b, physics_frames());
	}
	jb_lit(b, ",\"n\":");
	jb_i64(b, g_seq_out++);
	jb_lit(b, "}");
	send_payload(b->p, b->n);
}

// Check a received message (tag, then JSON with the expected sequence number) and
// parse it into a Dictionary variant. Returns 0 and stops the game when it is bad.
static int accept_message(const uint8_t *body, uint32_t n, Var *out) {
	uint8_t tag[32];
	hmac_sha256(g_key, sizeof g_key, body + 32, n - 32, tag);
	if (!tag_equal(tag, body)) {
		stop_game(EXIT_BAD_LINK, "unsigned message");
		return 0;
	}
	GS s;
	str_from(&s, (const char *)body + 32, n - 32);
	v_nil(out);
	const void *args[1] = {&s};
	f_ptrcall(mb_parse_json, NULL, args, out);
	dtor_string(&s);
	if (v_type(out) != T_DICT || (int64_t)dnum(out, &k_n, -1) != g_seq_in) {
		stop_game(EXIT_BAD_LINK, "bad message");
		return 0;
	}
	g_seq_in++;
	return 1;
}

// Lockstep: block until one whole message arrives. Returns 0 when the game stops.
static int recv_blocking(Var *out) {
	uint8_t hdr[4];
	if (!read_all(hdr, 4)) {
		stop_game(EXIT_LOST_LINK, "link lost");
		return 0;
	}
	uint32_t n = (uint32_t)hdr[0] << 24 | (uint32_t)hdr[1] << 16 | (uint32_t)hdr[2] << 8 | hdr[3];
	if (n < 32 || n > INBOUND_LIMIT) {
		stop_game(EXIT_BAD_LINK, "bad length");
		return 0;
	}
	uint8_t *body = malloc(n);
	if (!body || !read_all(body, n)) {
		free(body);
		stop_game(EXIT_LOST_LINK, "link lost");
		return 0;
	}
	int ok = accept_message(body, n, out);
	free(body);
	return ok;
}

// Realtime: read what has arrived without blocking.
static void pump_socket(void) {
	for (;;) {
		struct pollfd pfd = {g_sock, POLLIN, 0};
		if (poll(&pfd, 1, 0) <= 0 || !(pfd.revents & (POLLIN | POLLHUP | POLLERR))) return;
		if (g_in_cap - g_in_n < 65536) {
			size_t cap = g_in_cap ? g_in_cap * 2 : 262144;
			uint8_t *p = realloc(g_in, cap);
			if (!p) {
				stop_game(EXIT_LOST_LINK, "out of memory");
				return;
			}
			g_in = p;
			g_in_cap = cap;
		}
		ssize_t r = recv(g_sock, g_in + g_in_n, g_in_cap - g_in_n, 0);
		if (r < 0 && (errno == EINTR || errno == EAGAIN || errno == EWOULDBLOCK)) return;
		if (r <= 0) {
			stop_game(EXIT_LOST_LINK, "link lost");
			return;
		}
		g_in_n += (size_t)r;
	}
}

// Realtime: take the next complete message from the receive buffer, if any.
static int next_buffered(Var *out) {
	if (g_in_n < 4) return 0;
	uint32_t n = (uint32_t)g_in[0] << 24 | (uint32_t)g_in[1] << 16 | (uint32_t)g_in[2] << 8 | g_in[3];
	if (n < 32 || n > INBOUND_LIMIT) {
		stop_game(EXIT_BAD_LINK, "bad length");
		return 0;
	}
	if (g_in_n < 4 + (size_t)n) return 0;
	int ok = accept_message(g_in + 4, n, out);
	memmove(g_in, g_in + 4 + n, g_in_n - 4 - n);
	g_in_n -= 4 + n;
	return ok;
}

// ------------------------------------------------------------------ the game's console
static int find_devconsole(void) {
	if (g_devconsole_id && f_from_id(g_devconsole_id)) return 1;
	if (g_devconsole_id) {
		v_free(&g_devconsole);
		g_devconsole_id = 0;
		g_hooked = 0;
	}
	Obj root = NULL;
	if (g_tree) f_ptrcall(mb_get_root, g_tree, NULL, &root);
	if (!root) return 0;
	Var name, dc;
	v_text(&name, "DevConsole");
	ocall(root, &sn_get_node_or_null, &name, NULL, NULL, &dc);
	v_free(&name);
	Obj o = as_obj(&dc);
	if (!o) {
		v_free(&dc);
		return 0;
	}
	g_devconsole = dc;
	g_devconsole_id = f_instance_id(o);
	return 1;
}

static void on_event(void *ud, const GDExtensionConstVariantPtr *args, GDExtensionInt argc,
		GDExtensionVariantPtr r_ret, GDExtensionCallError *err) {
	(void)ud;
	(void)r_ret;
	err->error = GDEXTENSION_CALL_OK;
	if (!g_on || argc < 1) return;
	jbuf one;
	jb_init(&one, EVENT_LIMIT);
	jb_lit(&one, "{\"t\":");
	jb_i64(&one, physics_frames());
	jb_lit(&one, ",\"n\":");
	jw_var(&one, (const Var *)args[0], 0);
	jb_lit(&one, ",\"d\":");
	if (argc > 1) jw_var(&one, (const Var *)args[1], 0);
	else jb_lit(&one, "null");
	jb_lit(&one, "}");
	pthread_mutex_lock(&g_events_mu);
	if (one.over || g_events.n + one.n + 1 > EVENTS_LIMIT) {
		g_events_dropped++;
	} else {
		if (g_events.n) jb_raw(&g_events, ",", 1);
		jb_raw(&g_events, one.p, one.n);
	}
	pthread_mutex_unlock(&g_events_mu);
	jb_free(&one);
}

static void hook_events(void) {
	if (g_hooked || !find_devconsole()) return;
	g_hooked = 1;
	Var sig, has;
	v_text(&sig, "event");
	vcall(&g_devconsole, &sn_has_signal, (const Var *[]){&sig}, 1, &has);
	if (as_num(&has, 0) != 0) {
		Var cb, rc;
		custom_callable(on_event, NULL, &cb);
		vcall(&g_devconsole, &sn_connect, (const Var *[]){&sig, &cb}, 2, &rc);
		v_free(&rc);
		v_free(&cb);
	}
	v_free(&has);
	v_free(&sig);
}

// Run one DevConsole command and append {"cmd","res","t"} to the pending results. When
// the game has no DevConsole or the call itself fails, "res" is null and "unanswered"
// says why, so a broken console is never mistaken for a refusal it made itself.
static void run_dev(const Var *cmd, const Var *args, int64_t tick) {
	Var res;
	int ok = 0;
	if (find_devconsole()) ok = vcall(&g_devconsole, &sn_exec, (const Var *[]){cmd, args}, 2, &res);
	else v_nil(&res);
	if (g_dev.n) jb_raw(&g_dev, ",", 1);
	jb_lit(&g_dev, "{\"cmd\":");
	jw_var(&g_dev, cmd, 0);
	jb_lit(&g_dev, ",\"res\":");
	if (!g_devconsole_id) jb_lit(&g_dev, "null,\"unanswered\":\"no DevConsole\"");
	else if (!ok) jb_lit(&g_dev, "null,\"unanswered\":\"call failed\"");
	else jw_var(&g_dev, &res, 0);
	jb_lit(&g_dev, ",\"t\":");
	jb_i64(&g_dev, tick);
	jb_lit(&g_dev, "}");
	v_free(&res);
}

// ------------------------------------------------------------------ bones as shown
// A skeleton's modifiers (IK, look-at, ragdoll, a script's _process_modification_with_delta)
// act only while the engine updates the skeleton: it runs them, emits skeleton_updated,
// updates the skins, then puts the unmodified pose back. A read at the start of the next
// tick sees the pose without them. So the node follows each skeleton it reads: at every
// skeleton_updated it keeps the skeleton-space origin of each bone's global pose, and a read
// uses those when the skeleton updated during the last tick (or earlier in this one).
// Otherwise it reads the bones directly: a skeleton nothing changed does not update, and an
// update that changes no pose emits nothing and leaves the bones as they are.
typedef struct {
	GDObjectInstanceID id;  // the skeleton; 0 for a free slot
	int64_t used;           // tick of its latest read (main thread only)
	int64_t tick;           // tick of the latest update kept, -1 before the first
	int64_t count;          // the skeleton's bone count at that update
	int n;                  // bones kept: count, at most MAX_SHOWN_BONES
	float o[MAX_SHOWN_BONES][3];
} Shown;

// What one read of a skeleton's bones uses: n kept origins, or n == 0 to read directly.
typedef struct {
	int n;
	float o[MAX_SHOWN_BONES][3];
} BoneSnap;

static Shown g_shown[MAX_SHOWN];
// Guards the kept poses: an update runs on the thread that processes the skeleton.
static pthread_mutex_t g_shown_mu = PTHREAD_MUTEX_INITIALIZER;
_Static_assert(sizeof(void *) >= sizeof(GDObjectInstanceID), "instance id as callable userdata");

// The slot following skeleton id, or NULL. Slots change on the main thread only; other
// threads look them up with g_shown_mu held.
static Shown *shown_slot(GDObjectInstanceID id) {
	for (int i = 0; i < MAX_SHOWN; i++)
		if (g_shown[i].id == id) return &g_shown[i];
	return NULL;
}

// skeleton_updated of a followed skeleton (userdata: its instance id): keep its pose as
// the modifiers left it. No engine call is made with g_shown_mu held.
static void on_skeleton_updated(void *ud, const GDExtensionConstVariantPtr *args, GDExtensionInt argc,
		GDExtensionVariantPtr r_ret, GDExtensionCallError *err) {
	(void)args;
	(void)argc;
	(void)r_ret;
	err->error = GDEXTENSION_CALL_OK;
	GDObjectInstanceID id = (GDObjectInstanceID)(uintptr_t)ud;
	pthread_mutex_lock(&g_shown_mu);
	int followed = shown_slot(id) != NULL;
	pthread_mutex_unlock(&g_shown_mu);
	Obj sk = g_on && followed ? f_from_id(id) : NULL;
	if (!sk) return;
	int64_t count = 0;
	f_ptrcall(mb_bone_count, sk, NULL, &count);
	int n = count <= 0 ? 0 : count < MAX_SHOWN_BONES ? (int)count : MAX_SHOWN_BONES;
	float o[MAX_SHOWN_BONES][3];
	for (int64_t i = 0; i < n; i++) {
		Xf pose;
		const void *pa[1] = {&i};
		f_ptrcall(mb_bone_global_pose, sk, pa, &pose);
		memcpy(o[i], pose.o, sizeof o[i]);
	}
	int64_t tick = physics_frames();
	pthread_mutex_lock(&g_shown_mu);
	Shown *s = shown_slot(id);
	if (s) {
		memcpy(s->o, o, (size_t)n * sizeof o[0]);
		s->n = n;
		s->count = count;
		s->tick = tick;
	}
	pthread_mutex_unlock(&g_shown_mu);
}

// Connect (on) or disconnect (!on) the node's skeleton_updated callable for skeleton sk
// (instance id id) unless it already is so. Returns 1 when it is connected afterwards.
static int skeleton_hook(Obj sk, GDObjectInstanceID id, int on) {
	Var cb, has, rc;
	custom_callable(on_skeleton_updated, (void *)(uintptr_t)id, &cb);
	ocall(sk, &sn_is_connected, &k_skeleton_updated, &cb, NULL, &has);
	int connected = as_num(&has, 0) != 0;
	if (on && !connected) {
		connected = ocall(sk, &sn_connect, &k_skeleton_updated, &cb, NULL, &rc) && as_num(&rc, -1) == 0;
		v_free(&rc);
	} else if (!on && connected) {
		ocall(sk, &sn_disconnect, &k_skeleton_updated, &cb, NULL, &rc);
		v_free(&rc);
		connected = 0;
	}
	v_free(&has);
	v_free(&cb);
	return connected;
}

// Follow skeleton sk from now on (connecting once). Returns its slot, or NULL when every
// slot holds a skeleton read in this tick. A new skeleton takes a free slot, else one whose
// skeleton is gone, else the least recently read one (disconnected first). Main thread only.
static Shown *follow_skeleton(Obj sk, int64_t now) {
	GDObjectInstanceID id = f_instance_id(sk);
	Shown *s = shown_slot(id);
	if (!s && g_node) {
		Shown *lru = NULL;
		for (int i = 0; i < MAX_SHOWN && !s; i++) {
			Shown *c = &g_shown[i];
			if (!c->id || !f_from_id(c->id)) s = c;
			else if (c->used < now && (!lru || c->used < lru->used)) lru = c;
		}
		if (!s && lru) {
			Obj old = f_from_id(lru->id);
			if (old) skeleton_hook(old, lru->id, 0);
			s = lru;
		}
		if (s) {
			pthread_mutex_lock(&g_shown_mu);
			s->id = id;
			s->tick = -1;
			s->count = 0;
			s->n = 0;
			pthread_mutex_unlock(&g_shown_mu);
			skeleton_hook(sk, id, 1);
		}
	}
	if (s) s->used = now;
	return s;
}

// Prepare a read of skeleton sk's bones in this tick: the pose kept at its latest update
// when that update ran during the last tick (or earlier in this one), else nothing.
static void snap_bones(Obj sk, BoneSnap *snap) {
	snap->n = 0;
	int64_t now = physics_frames();
	Shown *s = follow_skeleton(sk, now);
	if (!s) return;
	int64_t count = 0;
	f_ptrcall(mb_bone_count, sk, NULL, &count);
	pthread_mutex_lock(&g_shown_mu);
	if (s->tick >= 0 && s->tick >= now - 1 && s->count == count) {
		snap->n = s->n;
		memcpy(snap->o, s->o, (size_t)s->n * sizeof s->o[0]);
	}
	pthread_mutex_unlock(&g_shown_mu);
}

// The skeleton-space origin of bone idx of sk as the game shows it (see snap_bones).
static void bone_origin(Obj sk, const BoneSnap *snap, int64_t idx, float out[3]) {
	if (idx >= 0 && idx < snap->n) {
		memcpy(out, snap->o[idx], sizeof snap->o[idx]);
		return;
	}
	Xf pose;
	const void *pa[1] = {&idx};
	f_ptrcall(mb_bone_global_pose, sk, pa, &pose);
	memcpy(out, pose.o, sizeof pose.o);
}

// Follow the skeleton of entity id ahead of the frame that reads it.
static void follow_entity(int64_t id) {
	Obj e = entity_by_id(id);
	Obj sk = e ? first_skeleton(e) : NULL;
	if (sk) follow_skeleton(sk, physics_frames());
}

// Follow the skeletons whose Head starts a line-of-sight query of the pending batch.
static void follow_queried(void) {
	int64_t n = asize(&g_pending_queries);
	for (int64_t i = 0; i < n; i++) {
		Var q, tv;
		aget(&g_pending_queries, i, &q);
		char *type = dget(&q, &k_type, &tv) ? as_text(&tv, NULL) : NULL;
		if (type && !strcmp(type, "los")) follow_entity((int64_t)dnum(&q, &k_a, -1));
		free(type);
		v_free(&tv);
		v_free(&q);
	}
}

// ------------------------------------------------------------------ observations
static void write_entity(jbuf *b, Obj o, Obj camera) {
	jb_lit(b, "{\"id\":");
	Var m = meta(o, &sn_m_id);
	jw_var(b, &m, 0);
	v_free(&m);
	jb_lit(b, ",\"k\":");
	m = meta(o, &sn_m_kind);
	jw_var(b, &m, 0);
	v_free(&m);
	jb_lit(b, ",\"a\":");
	m = meta(o, &sn_m_arch);
	jw_var(b, &m, 0);
	v_free(&m);
	jb_lit(b, ",\"f\":");
	m = meta(o, &sn_m_faction);
	jw_var(b, &m, 0);
	v_free(&m);
	if (is_class(o, &sn_node3d)) {
		Xf x = global_xf(o);
		jb_lit(b, ",\"p\":");
		jb_vec3(b, x.o[0], x.o[1], x.o[2]);
		jb_lit(b, ",\"bz\":");
		jb_vec3(b, x.r[0][2], x.r[1][2], x.r[2][2]);
		jb_lit(b, ",\"up\":");
		jb_f64(b, x.r[1][1]);
		V3 vel;
		int has_v = 0;
		if (is_class(o, &sn_rigid)) {
			f_ptrcall(mb_linear_velocity, o, NULL, &vel);
			has_v = 1;
		} else if (is_class(o, &sn_character)) {
			f_ptrcall(mb_real_velocity, o, NULL, &vel);
			has_v = 1;
		}
		if (has_v) {
			jb_lit(b, ",\"v\":");
			jb_vec3(b, vel.x, vel.y, vel.z);
		}
		if (camera) {
			V3 head = {x.o[0], x.o[1] + 1.0f, x.o[2]};
			GDExtensionBool in = 0;
			const void *args[1] = {&head};
			f_ptrcall(mb_in_frustum, camera, args, &in);
			jb_lit(b, ",\"iv\":");
			jb_bool(b, in);
		}
	}
	if (g_obs.n_meta > 0) {
		jb_lit(b, ",\"m\":{");
		int first = 1;
		for (int i = 0; i < g_obs.n_meta; i++) {
			if (!has_meta(o, &g_obs.meta[i])) continue;
			if (!first) jb_raw(b, ",", 1);
			first = 0;
			jb_cstr(b, g_obs.meta_txt[i]);
			jb_raw(b, ":", 1);
			m = meta(o, &g_obs.meta[i]);
			jw_var(b, &m, 0);
			v_free(&m);
		}
		jb_lit(b, "}");
	}
	jb_lit(b, "}");
}

static Obj current_camera(void) {
	if (!g_node) return NULL;
	Obj vp = NULL, cam = NULL;
	f_ptrcall(mb_get_viewport, g_node, NULL, &vp);
	if (vp) f_ptrcall(mb_camera_3d, vp, NULL, &cam);
	return cam;
}

// Whether entity o's "kind" metadata is one of the kinds the census lists.
static int kind_listed(Obj o) {
	if (!has_meta(o, &sn_m_kind)) return 0;
	Var m = meta(o, &sn_m_kind);
	char *t = as_text(&m, NULL);
	int found = 0;
	for (int i = 0; t && i < g_obs.n_kinds && !found; i++) found = !strcmp(t, g_obs.kind_txt[i]);
	free(t);
	v_free(&m);
	return found;
}

static void write_census(jbuf *b) {
	Obj cam = g_obs.view ? current_camera() : NULL;
	GA arr = group_nodes(&sn_entity);
	int64_t n = garr_size(&arr);
	jb_lit(b, ",\"census\":[");
	int first = 1;
	for (int64_t i = 0; i < n && !b->over; i++) {
		Obj o = garr_obj(&arr, i);
		if (!o || (g_obs.census_kinds && !kind_listed(o))) continue;
		if (!first) jb_raw(b, ",", 1);
		first = 0;
		write_entity(b, o, cam);
	}
	jb_lit(b, "]");
	dtor_array(&arr);
}

static void write_bones(jbuf *b) {
	jb_lit(b, ",\"bones\":{");
	int first = 1;
	BoneSnap snap;
	for (int i = 0; i < g_obs.n_bone_ids; i++) {
		Obj e = entity_by_id(g_obs.bone_ids[i]);
		Obj sk = e ? first_skeleton(e) : NULL;
		if (!sk) continue;
		snap_bones(sk, &snap);
		Xf skx = global_xf(sk);
		if (!first) jb_raw(b, ",", 1);
		first = 0;
		jb_raw(b, "\"", 1);
		jb_i64(b, g_obs.bone_ids[i]);
		jb_lit(b, "\":{");
		int bfirst = 1;
		for (int k = 0; k < g_obs.n_bone_names; k++) {
			int64_t idx = -1;
			const void *fa[1] = {&g_obs.bone_gs[k]};
			f_ptrcall(mb_find_bone, sk, fa, &idx);
			if (idx < 0) continue;
			float o[3];
			bone_origin(sk, &snap, idx, o);
			V3 w = xf_apply(&skx, o);
			if (!bfirst) jb_raw(b, ",", 1);
			bfirst = 0;
			jb_cstr(b, g_obs.bone_txt[k]);
			jb_raw(b, ":", 1);
			jb_vec3(b, w.x, w.y, w.z);
		}
		jb_lit(b, "}");
	}
	jb_lit(b, "}");
}

// Metadata key of o as a point: a Vector3, or an array of three numbers. Returns 1 and
// sets out when it is one.
static int meta_point(Obj o, const SN *key, float out[3]) {
	if (!has_meta(o, key)) return 0;
	Var m = meta(o, key);
	int ok = 0;
	if (v_type(&m) == T_V3) {
		vto[T_V3](out, (GDExtensionVariantPtr)&m);
		ok = 1;
	} else if (asize(&m) == 3) {
		ok = 1;
		for (int i = 0; i < 3 && ok; i++) {
			Var e;
			int t = aget(&m, i, &e) ? v_type(&e) : T_NIL;
			ok = t == T_INT || t == T_FLOAT;
			if (ok) out[i] = (float)as_num(&e, 0);
			v_free(&e);
		}
	}
	v_free(&m);
	return ok;
}

// A seat's point metadata (in vehicle space) in world space, or null when the marker has
// no such point or the vehicle has no transform (vx NULL).
static void write_seat_point(jbuf *b, Obj marker, const SN *key, const Xf *vx) {
	float p[3] = {0, 0, 0};
	if (vx && meta_point(marker, key, p)) {
		V3 w = xf_apply(vx, p);
		jb_vec3(b, w.x, w.y, w.z);
	} else {
		jb_lit(b, "null");
	}
}

// For each observed vehicle, the Marker3D nodes under it (any depth) in group "seat", in
// tree order: the "index" metadata as written, the marker's world origin, and the "door"
// and "wheel" metadata (points in the vehicle's space) in world space.
static void write_seats(jbuf *b) {
	jb_lit(b, ",\"seats\":{");
	int first = 1;
	for (int i = 0; i < g_obs.n_seat_ids && !b->over; i++) {
		Obj e = entity_by_id(g_obs.seat_ids[i]);
		if (!e) continue;
		Xf vx;
		memset(&vx, 0, sizeof vx);
		int spatial = is_class(e, &sn_node3d);
		if (spatial) vx = global_xf(e);
		if (!first) jb_raw(b, ",", 1);
		first = 0;
		jb_raw(b, "\"", 1);
		jb_i64(b, g_obs.seat_ids[i]);
		jb_lit(b, "\":[");
		GA marks = find_children(e, "Marker3D");
		int64_t n = garr_size(&marks);
		int sfirst = 1;
		for (int64_t k = 0; k < n && !b->over; k++) {
			Obj m = garr_obj(&marks, k);
			if (!m || !in_group(m, &sn_seat)) continue;
			if (!sfirst) jb_raw(b, ",", 1);
			sfirst = 0;
			jb_lit(b, "{\"index\":");
			if (has_meta(m, &sn_m_index)) {
				Var v = meta(m, &sn_m_index);
				jw_var(b, &v, 0);
				v_free(&v);
			} else {
				jb_lit(b, "null");
			}
			Xf mx = global_xf(m);
			jb_lit(b, ",\"p\":");
			jb_vec3(b, mx.o[0], mx.o[1], mx.o[2]);
			jb_lit(b, ",\"door\":");
			write_seat_point(b, m, &sn_m_door, spatial ? &vx : NULL);
			jb_lit(b, ",\"wheel\":");
			write_seat_point(b, m, &sn_m_wheel, spatial ? &vx : NULL);
			jb_lit(b, "}");
		}
		dtor_array(&marks);
		jb_lit(b, "]");
	}
	jb_lit(b, "}");
}

static void write_camera(jbuf *b) {
	Obj cam = current_camera();
	jb_lit(b, ",\"camera\":");
	if (!cam) {
		jb_lit(b, "null");
		return;
	}
	Xf x = global_xf(cam);
	Var fov;
	ocall(cam, &sn_get_fov, NULL, NULL, NULL, &fov);
	jb_lit(b, "{\"p\":");
	jb_vec3(b, x.o[0], x.o[1], x.o[2]);
	jb_lit(b, ",\"bz\":");
	jb_vec3(b, x.r[0][2], x.r[1][2], x.r[2][2]);
	jb_lit(b, ",\"fov\":");
	jb_f64(b, as_num(&fov, 0));
	jb_lit(b, "}");
	v_free(&fov);
}

static void write_hud(jbuf *b) {
	jb_lit(b, ",\"hud\":{");
	int first = 1;
	for (int i = 0; i < g_obs.n_hud; i++) {
		GA arr = group_nodes(&g_obs.hud[i]);
		Obj o = garr_size(&arr) > 0 ? garr_obj(&arr, 0) : NULL;
		dtor_array(&arr);
		if (!o) continue;
		if (!first) jb_raw(b, ",", 1);
		first = 0;
		jb_cstr(b, g_obs.hud_txt[i]);
		Var vis, text, kids;
		ocall(o, &sn_is_visible, NULL, NULL, NULL, &vis);
		ocall(o, &sn_get, &k_text, NULL, NULL, &text);
		ocall(o, &sn_get_children, NULL, NULL, NULL, &kids);
		int64_t shown = 0, n = asize(&kids);
		for (int64_t c = 0; c < n; c++) {
			Var kid, kv;
			aget(&kids, c, &kid);
			Obj ko = as_obj(&kid);
			if (ko) {
				if (ocall(ko, &sn_is_visible, NULL, NULL, NULL, &kv) && as_num(&kv, 0) != 0) shown++;
				v_free(&kv);
			}
			v_free(&kid);
		}
		jb_lit(b, ":{\"vis\":");
		jb_bool(b, as_num(&vis, 0) != 0);
		jb_lit(b, ",\"shown\":");
		jb_i64(b, shown);
		jb_lit(b, ",\"text\":");
		jw_var(b, &text, 0);
		jb_lit(b, "}");
		v_free(&vis);
		v_free(&text);
		v_free(&kids);
	}
	jb_lit(b, "}");
}

static void write_state(jbuf *b) {
	jb_lit(b, ",\"state\":");
	Var cmd, args, res;
	v_nil(&res);
	v_text(&cmd, "state");
	GDExtensionCallError e = {0};
	f_v_construct(GDEXTENSION_VARIANT_TYPE_DICTIONARY, &args, NULL, 0, &e);
	if (find_devconsole() && vcall(&g_devconsole, &sn_exec, (const Var *[]){&cmd, &args}, 2, &res)) {
		jw_var(b, &res, 0);
	} else {
		jb_lit(b, "null");
	}
	v_free(&res);
	v_free(&args);
	v_free(&cmd);
}

// ------------------------------------------------------------------ queries
static Var g_space;   // the physics space of the current query batch
static Var g_params;  // one PhysicsRayQueryParameters3D reused within the batch
static int g_space_ok;

static int load_space(void) {
	if (g_space_ok) return 1;
	Obj vp = NULL;
	if (g_node) f_ptrcall(mb_get_viewport, g_node, NULL, &vp);
	if (!vp) return 0;
	Var world;
	ocall(vp, &sn_find_world, NULL, NULL, NULL, &world);
	int ok = vcall(&world, &sn_space_state, NULL, 0, &g_space) && v_type(&g_space) == T_OBJECT;
	v_free(&world);
	if (!ok) {
		v_free(&g_space);
		return 0;
	}
	Var cls, cdb;
	v_text(&cls, "PhysicsRayQueryParameters3D");
	v_obj(&cdb, singleton("ClassDB"));
	ok = vcall(&cdb, &sn_instantiate, (const Var *[]){&cls}, 1, &g_params) && v_type(&g_params) == T_OBJECT;
	v_free(&cdb);
	v_free(&cls);
	if (!ok) {
		v_free(&g_params);
		v_free(&g_space);
		return 0;
	}
	g_space_ok = 1;
	return 1;
}

static void write_collider_meta(jbuf *b, Obj c) {
	Var m;
	if (has_meta(c, &sn_m_surface)) {
		m = meta(c, &sn_m_surface);
		jb_lit(b, ",\"surface\":");
		jw_var(b, &m, 0);
		v_free(&m);
	}
	if (has_meta(c, &sn_m_parcel)) {
		m = meta(c, &sn_m_parcel);
		jb_lit(b, ",\"parcel\":");
		jw_var(b, &m, 0);
		v_free(&m);
	}
	Obj e = c;
	for (int up = 0; e && up < 8; up++) {
		if (has_meta(e, &sn_m_id)) {
			m = meta(e, &sn_m_id);
			jb_lit(b, ",\"entity\":");
			jw_var(b, &m, 0);
			v_free(&m);
			break;
		}
		Obj parent = NULL;
		f_ptrcall(mb_get_parent, e, NULL, &parent);
		e = parent;
	}
}

// Cast one ray; writes {"hit": false} or {"hit": true, "p": [...], ...}. Returns the
// hit flag and, when hit_p is given, the hit point.
static int write_ray(jbuf *b, V3 from, V3 to, int64_t mask, V3 *hit_p) {
	if (!load_space()) {
		jb_lit(b, "{\"hit\":false}");
		return 0;
	}
	Var vf, vt, vm, rc, res;
	Var *params = &g_params;
	v_vec3(&vf, from);
	v_vec3(&vt, to);
	v_int(&vm, mask);
	vcall(params, &sn_set_from, (const Var *[]){&vf}, 1, &rc);
	v_free(&rc);
	vcall(params, &sn_set_to, (const Var *[]){&vt}, 1, &rc);
	v_free(&rc);
	vcall(params, &sn_set_mask, (const Var *[]){&vm}, 1, &rc);
	v_free(&rc);
	vcall(&g_space, &sn_intersect_ray, (const Var *[]){params}, 1, &res);
	Var pos, col;
	int hit = dget(&res, &k_position, &pos);
	if (!hit) {
		jb_lit(b, "{\"hit\":false}");
	} else {
		float f[3];
		vto[T_V3](f, &pos);
		if (hit_p) {
			hit_p->x = f[0];
			hit_p->y = f[1];
			hit_p->z = f[2];
		}
		jb_lit(b, "{\"hit\":true,\"p\":");
		jb_vec3(b, f[0], f[1], f[2]);
		if (dget(&res, &k_collider, &col)) {
			Obj c = as_obj(&col);
			if (c) write_collider_meta(b, c);
		}
		v_free(&col);
		jb_lit(b, "}");
	}
	v_free(&pos);
	v_free(&res);
	v_free(&vm);
	v_free(&vt);
	v_free(&vf);
	return hit;
}

static void query_los(jbuf *b, const Var *q) {
	Obj ea = entity_by_id((int64_t)dnum(q, &k_a, -1));
	Obj eb = entity_by_id((int64_t)dnum(q, &k_b, -1));
	if (!ea || !eb) {
		jb_lit(b, "{\"ok\":false}");
		return;
	}
	Xf xa = global_xf(ea), xb = global_xf(eb);
	float up_a = (float)dnum(q, &k_a_up, 1.65), up_b = (float)dnum(q, &k_b_up, 0.8);
	V3 pa = {xa.o[0], xa.o[1] + up_a, xa.o[2]};
	V3 pb = {xb.o[0], xb.o[1] + up_b, xb.o[2]};
	Obj sk = first_skeleton(ea);
	if (sk) {
		GS head;
		str_from(&head, "Head", 4);
		int64_t idx = -1;
		const void *fa[1] = {&head};
		f_ptrcall(mb_find_bone, sk, fa, &idx);
		dtor_string(&head);
		if (idx >= 0) {
			BoneSnap snap;
			snap_bones(sk, &snap);
			float o[3];
			bone_origin(sk, &snap, idx, o);
			Xf skx = global_xf(sk);
			pa = xf_apply(&skx, o);
		}
	}
	jbuf tmp;
	jb_init(&tmp, 4096);
	int hit = write_ray(&tmp, pa, pb, (int64_t)dnum(q, &k_mask, 1), NULL);
	jb_free(&tmp);
	float dx = pb.x - pa.x, dy = pb.y - pa.y, dz = pb.z - pa.z;
	jb_lit(b, "{\"ok\":true,\"clear\":");
	jb_bool(b, !hit);
	jb_lit(b, ",\"from\":");
	jb_vec3(b, pa.x, pa.y, pa.z);
	jb_lit(b, ",\"dist\":");
	jb_f64(b, sqrt((double)dx * dx + (double)dy * dy + (double)dz * dz));
	jb_lit(b, "}");
}

static void query_skeleton(jbuf *b, const Var *q) {
	Obj e = entity_by_id((int64_t)dnum(q, &k_entity, -1));
	if (!e) {
		jb_lit(b, "{\"ok\":false}");
		return;
	}
	GA sks = find_children(e, "Skeleton3D");
	int64_t n_sk = garr_size(&sks);
	Obj sk = n_sk > 0 ? garr_obj(&sks, 0) : NULL;
	dtor_array(&sks);
	jb_lit(b, "{\"ok\":true,\"skeletons\":");
	jb_i64(b, n_sk);
	if (!sk) {
		jb_lit(b, "}");
		return;
	}
	int64_t nb = 0;
	f_ptrcall(mb_bone_count, sk, NULL, &nb);
	jb_lit(b, ",\"bones\":[");
	for (int64_t i = 0; i < nb; i++) {
		Var vi, name;
		v_int(&vi, i);
		ocall(sk, &sn_get_bone_name, &vi, NULL, NULL, &name);
		if (i) jb_raw(b, ",", 1);
		jw_var(b, &name, 0);
		v_free(&name);
		v_free(&vi);
	}
	jb_lit(b, "]");
	GA meshes = find_children(e, "MeshInstance3D");
	int64_t nm = garr_size(&meshes), bound = 0, tris = 0;
	GDObjectInstanceID sk_id = f_instance_id(sk);
	for (int64_t i = 0; i < nm; i++) {
		Obj mi = garr_obj(&meshes, i);
		if (!mi) continue;
		Var skin, path, target, mesh;
		ocall(mi, &sn_get_skin, NULL, NULL, NULL, &skin);
		ocall(mi, &sn_get_skeleton_path, NULL, NULL, NULL, &path);
		ocall(mi, &sn_get_node_or_null, &path, NULL, NULL, &target);
		ocall(mi, &sn_get_mesh, NULL, NULL, NULL, &mesh);
		Obj to = as_obj(&target);
		if (as_obj(&skin) && to && f_instance_id(to) == sk_id && as_obj(&mesh)) {
			Var count;
			vcall(&mesh, &sn_surface_count, NULL, 0, &count);
			int64_t ns = (int64_t)as_num(&count, 0), has_bones = 0;
			v_free(&count);
			for (int64_t s = 0; s < ns; s++) {
				Var vs, arrays, bones, index;
				v_int(&vs, s);
				vcall(&mesh, &sn_surface_arrays, (const Var *[]){&vs}, 1, &arrays);
				if (aget(&arrays, 10, &bones) && asize(&bones) > 0) has_bones = 1;
				if (aget(&arrays, 12, &index)) tris += asize(&index) / 3;
				v_free(&index);
				v_free(&bones);
				v_free(&arrays);
				v_free(&vs);
			}
			if (has_bones) bound++;
		}
		v_free(&mesh);
		v_free(&target);
		v_free(&path);
		v_free(&skin);
	}
	dtor_array(&meshes);
	jb_lit(b, ",\"bound_meshes\":");
	jb_i64(b, bound);
	jb_lit(b, ",\"triangles\":");
	jb_i64(b, tris);
	jb_lit(b, "}");
}

static void query_unregistered(jbuf *b) {
	static const char *classes[3] = {"Skeleton3D", "CharacterBody3D", "VehicleBody3D"};
	Obj root = NULL;
	if (g_tree) f_ptrcall(mb_get_root, g_tree, NULL, &root);
	jb_lit(b, "[");
	int first = 1;
	for (int c = 0; c < 3 && root; c++) {
		GA arr = find_children(root, classes[c]);
		int64_t n = garr_size(&arr);
		for (int64_t i = 0; i < n; i++) {
			Obj o = garr_obj(&arr, i);
			int registered = 0;
			for (Obj e = o; e && !registered;) {
				GDExtensionBool in = 0;
				const void *args[1] = {&sn_entity};
				f_ptrcall(mb_is_in_group, e, args, &in);
				registered = in != 0;
				Obj parent = NULL;
				f_ptrcall(mb_get_parent, e, NULL, &parent);
				e = parent;
			}
			if (registered || !o) continue;
			Var path;
			ocall(o, &sn_get_path, NULL, NULL, NULL, &path);
			if (!first) jb_raw(b, ",", 1);
			first = 0;
			jw_var(b, &path, 0);
			v_free(&path);
		}
		dtor_array(&arr);
	}
	jb_lit(b, "]");
}

static void query_meta(jbuf *b, const Var *q) {
	Obj e = entity_by_id((int64_t)dnum(q, &k_entity, -1));
	Var keys;
	dget(q, &k_keys, &keys);
	if (!e) {
		jb_lit(b, "{\"ok\":false}");
		v_free(&keys);
		return;
	}
	jb_lit(b, "{\"ok\":true");
	int64_t n = asize(&keys);
	for (int64_t i = 0; i < n; i++) {
		Var k;
		aget(&keys, i, &k);
		size_t len;
		char *t = as_text(&k, &len);
		SN key;
		f_sn_new(&key, t ? t : "", 0);
		jb_raw(b, ",", 1);
		jb_str(b, t ? t : "", len);
		jb_raw(b, ":", 1);
		if (has_meta(e, &key)) {
			Var m = meta(e, &key);
			jw_var(b, &m, 0);
			v_free(&m);
		} else {
			jb_lit(b, "null");
		}
		dtor_sname(&key);
		free(t);
		v_free(&k);
	}
	jb_lit(b, "}");
	v_free(&keys);
}

// A property of o read by name, when it is a number; null otherwise (or when o has none).
static void write_number_property(jbuf *b, Obj o, const Var *name) {
	Var v;
	ocall(o, &sn_get, name, NULL, NULL, &v);
	int t = v_type(&v);
	if (t == T_INT || t == T_FLOAT) jw_var(b, &v, 0);
	else jb_lit(b, "null");
	v_free(&v);
}

// An entity's node: its class, whether it is a physics body (a CollisionObject3D), and its
// mass, collision layer and collision mask properties.
static void query_body(jbuf *b, const Var *q) {
	Obj e = entity_by_id((int64_t)dnum(q, &k_entity, -1));
	if (!e) {
		jb_lit(b, "{\"ok\":false}");
		return;
	}
	Var cls;
	ocall(e, &sn_get_class, NULL, NULL, NULL, &cls);
	jb_lit(b, "{\"ok\":true,\"class\":");
	jw_var(b, &cls, 0);
	v_free(&cls);
	jb_lit(b, ",\"physics\":");
	jb_bool(b, is_class(e, &sn_collision_object));
	jb_lit(b, ",\"mass\":");
	write_number_property(b, e, &k_mass);
	jb_lit(b, ",\"layer\":");
	write_number_property(b, e, &k_collision_layer);
	jb_lit(b, ",\"mask\":");
	write_number_property(b, e, &k_collision_mask);
	jb_lit(b, "}");
}

static void write_queries(jbuf *b) {
	int64_t n = asize(&g_pending_queries);
	if (n <= 0) return;
	g_space_ok = 0;
	jb_lit(b, ",\"q\":{");
	for (int64_t i = 0; i < n && !b->over; i++) {
		Var q, idv, tv;
		aget(&g_pending_queries, i, &q);
		if (i) jb_raw(b, ",", 1);
		if (dget(&q, &k_id, &idv)) jw_text_of(b, &idv);
		else {
			jb_lit(b, "\"q");
			jb_i64(b, i);
			jb_lit(b, "\"");
		}
		jb_raw(b, ":", 1);
		char *type = dget(&q, &k_type, &tv) ? as_text(&tv, NULL) : NULL;
		if (!type) {
			jb_lit(b, "null");
		} else if (!strcmp(type, "ray")) {
			Var fv, tov;
			dget(&q, &k_from, &fv);
			dget(&q, &k_to, &tov);
			write_ray(b, as_vec3(&fv), as_vec3(&tov), (int64_t)dnum(&q, &k_mask, 1), NULL);
			v_free(&fv);
			v_free(&tov);
		} else if (!strcmp(type, "down")) {
			Var pts;
			dget(&q, &k_points, &pts);
			double y0 = dnum(&q, &k_y0, 80.0), y1 = dnum(&q, &k_y1, -5.0);
			int64_t mask = (int64_t)dnum(&q, &k_mask, 1), np = asize(&pts);
			jb_lit(b, "[");
			for (int64_t k = 0; k < np && !b->over; k++) {
				Var pt, px, pz;
				aget(&pts, k, &pt);
				aget(&pt, 0, &px);
				aget(&pt, 1, &pz);
				float x = (float)as_num(&px, 0), z = (float)as_num(&pz, 0);
				if (k) jb_raw(b, ",", 1);
				V3 a = {x, (float)y0, z}, c = {x, (float)y1, z};
				write_ray(b, a, c, mask, NULL);
				v_free(&pz);
				v_free(&px);
				v_free(&pt);
			}
			jb_lit(b, "]");
			v_free(&pts);
		} else if (!strcmp(type, "los")) {
			query_los(b, &q);
		} else if (!strcmp(type, "skeleton")) {
			query_skeleton(b, &q);
		} else if (!strcmp(type, "unregistered")) {
			query_unregistered(b);
		} else if (!strcmp(type, "meta")) {
			query_meta(b, &q);
		} else if (!strcmp(type, "body")) {
			query_body(b, &q);
		} else {
			jb_lit(b, "null");
		}
		free(type);
		v_free(&tv);
		v_free(&idv);
		v_free(&q);
	}
	jb_lit(b, "}");
	if (g_space_ok) {
		v_free(&g_params);
		v_free(&g_space);
	}
	g_space_ok = 0;
	v_free(&g_pending_queries);
	v_nil(&g_pending_queries);
}

// ------------------------------------------------------------------ frames
static void take_events(jbuf *b) {
	pthread_mutex_lock(&g_events_mu);
	jb_lit(b, ",\"events\":[");
	jb_raw(b, g_events.p, g_events.n);
	jb_lit(b, "]");
	jb_clear(&g_events);
	if (g_events_dropped) {
		jb_lit(b, ",\"dropped\":");
		jb_i64(b, g_events_dropped);
		g_events_dropped = 0;
	}
	pthread_mutex_unlock(&g_events_mu);
}

static void send_frame(int64_t t) {
	uint64_t us = now_us();
	jbuf *b = &g_frame;
	jb_clear(b);
	jb_lit(b, "{\"t\":");
	jb_i64(b, t);
	jb_lit(b, ",\"ticks\":");
	jb_i64(b, g_ticks_seen);
	take_events(b);
	jb_lit(b, ",\"dev\":[");
	jb_raw(b, g_dev.p, g_dev.n);
	jb_lit(b, "]");
	jb_clear(&g_dev);
	if (g_obs.census) write_census(b);
	if (g_obs.n_bone_ids > 0) write_bones(b);
	if (g_obs.n_seat_ids > 0) write_seats(b);
	if (g_obs.camera) write_camera(b);
	if (g_obs.n_hud > 0) write_hud(b);
	if (g_obs.state) write_state(b);
	write_queries(b);
	jb_lit(b, ",\"perf\":{\"wall_us\":");
	jb_i64(b, g_last_frame_us ? (int64_t)(us - g_last_frame_us) : 0);
	jb_lit(b, ",\"own_us\":");
	jb_i64(b, (int64_t)g_own_us);
	jb_lit(b, ",\"frame_us\":");
	jb_i64(b, (int64_t)(now_us() - us));
	jb_lit(b, "}");
	if (g_realtime) {
		jb_lit(b, ",\"us\":");
		jb_i64(b, (int64_t)us);
	}
	g_last_frame_us = us;
	g_last_frame_tick = t;
	g_ticks_seen = 0;
	send_frame_buf(b);
}

static void send_hello(void) {
	jbuf b;
	jb_init(&b, 1 << 20);
	Var r, a0, a1;
	Obj engine = singleton("Engine"), ps = singleton("ProjectSettings"), os = singleton("OS");
	jb_lit(&b, "{\"hello\":{\"native\":true,\"mode\":");
	jb_cstr(&b, g_realtime ? "realtime" : "lockstep");
	jb_lit(&b, ",\"pid\":");
	jb_i64(&b, (int64_t)getpid());
	ocall(engine, &sn_get_version_info, NULL, NULL, NULL, &r);
	v_text(&a0, "string");
	Var ver;
	dget(&r, &a0, &ver);
	jb_lit(&b, ",\"engine\":");
	jw_var(&b, &ver, 0);
	v_free(&ver);
	v_free(&a0);
	v_free(&r);
	static const char *settings[5][2] = {
		{"physics_engine", "physics/3d/physics_engine"},
		{"separate_thread", "physics/3d/run_on_separate_thread"},
		{"worker_threads", "threading/worker_pool/max_threads"},
		{"renderer_setting", "rendering/renderer/rendering_method"},
		{"file_logging", "debug/file_logging/enable_file_logging"},
	};
	for (int i = 0; i < 5; i++) {
		v_text(&a0, settings[i][1]);
		v_nil(&a1);
		ocall(ps, &sn_get_setting, &a0, &a1, NULL, &r);
		jb_lit(&b, ",");
		jb_cstr(&b, settings[i][0]);
		jb_lit(&b, ":");
		jw_var(&b, &r, 0);
		v_free(&r);
		v_free(&a1);
		v_free(&a0);
	}
	ocall(engine, &sn_get_ticks, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"ticks\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	ocall(engine, &sn_get_jitter, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"jitter_fix\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	ocall(engine, &sn_get_max_steps, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"max_physics_steps\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	ocall(singleton("RenderingServer"), &sn_render_method, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"renderer\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	ocall(singleton("DisplayServer"), &sn_display_name, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"display\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	ocall(os, &sn_cpu_count, NULL, NULL, NULL, &r);
	jb_lit(&b, ",\"cpus\":");
	jw_var(&b, &r, 0);
	v_free(&r);
	static const char *envs[3] = {"QA_TELEMETRY_KEY", "QA_TELEMETRY_PORT", "QA_TELEMETRY_MODE"};
	int visible = 0;
	for (int i = 0; i < 3; i++) {
		v_text(&a0, envs[i]);
		ocall(os, &sn_get_env, &a0, NULL, NULL, &r);
		size_t n = 0;
		char *t = as_text(&r, &n);
		if (n > 0) visible++;
		free(t);
		v_free(&r);
		v_free(&a0);
	}
	jb_lit(&b, ",\"settings_in_environment\":");
	jb_i64(&b, visible);
	int64_t index = -1;
	GDExtensionBool internal = 0;
	const void *ia[1] = {&internal};
	f_ptrcall(mb_get_index, g_node, ia, &index);
	jb_lit(&b, ",\"first_autoload\":");
	jb_bool(&b, index == 0);
	jb_lit(&b, "}");
	send_frame_buf(&b);
	jb_free(&b);
}

static void send_heartbeat(int64_t t) {
	char p[96];
	int n = snprintf(p, sizeof p, "{\"hb\":%lld,\"us\":%llu,\"n\":%lld}", (long long)t,
			(unsigned long long)now_us(), (long long)g_seq_out++);
	send_payload(p, (size_t)n);
}

static void send_gone(void) {
	if (!g_on || g_closing) return;
	char p[96];
	int n = snprintf(p, sizeof p, "{\"gone\":%lld,\"n\":%lld}", (long long)physics_frames(),
			(long long)g_seq_out++);
	send_payload(p, (size_t)n);
	g_on = 0;
}

// ------------------------------------------------------------------ commands
static void clear_inputs(void) {
	for (int i = 0; i < g_n_inputs; i++) v_free(&g_inputs[i].action);
	g_n_inputs = 0;
}

static void set_inputs(const Var *list) {
	clear_inputs();
	int64_t n = asize(list);
	if (n > g_cap_inputs) {
		Input *p = realloc(g_inputs, (size_t)n * sizeof(Input));
		if (!p) return;
		g_inputs = p;
		g_cap_inputs = (int)n;
	}
	for (int64_t i = 0; i < n; i++) {
		Var e, off, act, str;
		aget(list, i, &e);
		aget(&e, 0, &off);
		aget(&e, 1, &act);
		aget(&e, 2, &str);
		Input *in = &g_inputs[g_n_inputs++];
		in->off = (int64_t)as_num(&off, -1);
		f_v_copy(&in->action, &act);
		in->strength = as_num(&str, 0);
		v_free(&str);
		v_free(&act);
		v_free(&off);
		v_free(&e);
	}
}

static void free_observe(void) {
	for (int i = 0; i < g_obs.n_meta; i++) {
		dtor_sname(&g_obs.meta[i]);
		free(g_obs.meta_txt[i]);
	}
	for (int i = 0; i < g_obs.n_kinds; i++) {
		dtor_sname(&g_obs.kinds[i]);
		free(g_obs.kind_txt[i]);
	}
	for (int i = 0; i < g_obs.n_bone_names; i++) {
		dtor_string(&g_obs.bone_gs[i]);
		free(g_obs.bone_txt[i]);
	}
	for (int i = 0; i < g_obs.n_hud; i++) {
		dtor_sname(&g_obs.hud[i]);
		free(g_obs.hud_txt[i]);
	}
	int every = g_obs.every;
	memset(&g_obs, 0, sizeof g_obs);
	g_obs.every = every;
}

// Read a list of names from field key of dict into StringNames (and their text).
static int names_into(const Var *dict, const Var *key, SN *out, char **txt, int max) {
	Var list;
	int n = 0;
	if (dget(dict, key, &list)) {
		int64_t m = asize(&list);
		for (int64_t i = 0; i < m && n < max; i++) {
			Var e;
			aget(&list, i, &e);
			size_t len;
			char *t = as_text(&e, &len);
			if (t) {
				f_sn_new(&out[n], t, 0);
				txt[n++] = t;
			}
			v_free(&e);
		}
	}
	v_free(&list);
	return n;
}

static void set_observe(const Var *o) {
	free_observe();
	Var c;
	if (dget(o, &k_census, &c)) {
		g_obs.census = v_type(&c) == T_DICT || as_num(&c, 0) != 0;
		if (v_type(&c) == T_DICT) {
			g_obs.view = dnum(&c, &k_view, 0) != 0;
			g_obs.n_meta = names_into(&c, &k_meta, g_obs.meta, g_obs.meta_txt, MAX_KEYS);
			Var kinds;  // a list of kinds (even an empty one) limits the census to them
			g_obs.census_kinds = dget(&c, &k_kinds, &kinds) && v_type(&kinds) == T_ARRAY;
			v_free(&kinds);
			g_obs.n_kinds = names_into(&c, &k_kinds, g_obs.kinds, g_obs.kind_txt, MAX_KEYS);
		}
	}
	v_free(&c);
	Var bones;
	if (dget(o, &k_bones, &bones)) {
		Var ids, names;
		dget(&bones, &k_ids, &ids);
		int64_t n = asize(&ids);
		for (int64_t i = 0; i < n && g_obs.n_bone_ids < MAX_BONE_IDS; i++) {
			Var e;
			aget(&ids, i, &e);
			g_obs.bone_ids[g_obs.n_bone_ids++] = (int64_t)as_num(&e, -1);
			v_free(&e);
		}
		dget(&bones, &k_names, &names);
		n = asize(&names);
		for (int64_t i = 0; i < n && g_obs.n_bone_names < MAX_BONE_NAMES; i++) {
			Var e;
			aget(&names, i, &e);
			size_t len;
			char *t = as_text(&e, &len);
			if (t) {
				str_from(&g_obs.bone_gs[g_obs.n_bone_names], t, len);
				g_obs.bone_txt[g_obs.n_bone_names++] = t;
			}
			v_free(&e);
		}
		v_free(&names);
		v_free(&ids);
	}
	v_free(&bones);
	Var seats;
	if (dget(o, &k_seats, &seats)) {
		Var ids;
		dget(&seats, &k_ids, &ids);
		int64_t n = asize(&ids);
		for (int64_t i = 0; i < n && g_obs.n_seat_ids < MAX_SEAT_IDS; i++) {
			Var e;
			int64_t id = 0;
			aget(&ids, i, &e);
			int skip = !as_id(&e, &id);  // not a whole number, or listed already
			for (int k = 0; k < g_obs.n_seat_ids && !skip; k++) skip = g_obs.seat_ids[k] == id;
			if (!skip) g_obs.seat_ids[g_obs.n_seat_ids++] = id;
			v_free(&e);
		}
		v_free(&ids);
	}
	v_free(&seats);
	g_obs.camera = dnum(o, &k_camera, 0) != 0;
	g_obs.state = dnum(o, &k_state, 0) != 0;
	g_obs.n_hud = names_into(o, &k_hud, g_obs.hud, g_obs.hud_txt, MAX_KEYS);
	int every = (int)dnum(o, &k_every, g_obs.every > 0 ? g_obs.every : 6);
	g_obs.every = every < 1 ? 1 : every;
}

// Apply one command at tick t. Returns 0 when the command stops the game.
static int apply_command(const Var *cmd, int64_t t) {
	Var v;
	if (dget(cmd, &k_quit, &v) && as_num(&v, 0) != 0) {
		v_free(&v);
		g_closing = 1;
		g_on = 0;
		int64_t code = 0;
		const void *args[1] = {&code};
		if (g_tree) f_ptrcall(mb_quit, g_tree, args, NULL);
		return 0;
	}
	v_free(&v);
	g_cmd_tick = t;
	double run = dnum(cmd, &k_run, 1);
	g_left = run < 1 ? 1 : run > 1e7 ? 10000000 : (int64_t)run;
	if (dget(cmd, &k_inputs, &v)) set_inputs(&v);
	else clear_inputs();
	v_free(&v);
	int new_observe = 0, new_queries = 0;
	if (dget(cmd, &k_observe, &v)) {
		set_observe(&v);
		new_observe = 1;
	}
	v_free(&v);
	if (dget(cmd, &k_queries, &v) && asize(&v) > 0) {
		v_free(&g_pending_queries);
		f_v_copy(&g_pending_queries, &v);
		new_queries = 1;
	}
	v_free(&v);
	if (dget(cmd, &k_dev, &v)) {
		int64_t n = asize(&v);
		for (int64_t i = 0; i < n && g_on; i++) {
			Var e, name, args;
			aget(&v, i, &e);
			aget(&e, 0, &name);
			if (!aget(&e, 1, &args) || v_type(&args) == T_NIL) {
				v_free(&args);
				GDExtensionCallError err = {0};
				f_v_construct(GDEXTENSION_VARIANT_TYPE_DICTIONARY, &args, NULL, 0, &err);
			}
			run_dev(&name, &args, t);
			v_free(&args);
			v_free(&name);
			v_free(&e);
		}
	}
	v_free(&v);
	// Follow the skeletons the next frame reads now, so that it already has their pose as
	// shown (after the commands above, which may have made them).
	for (int i = 0; new_observe && g_on && i < g_obs.n_bone_ids; i++) follow_entity(g_obs.bone_ids[i]);
	if (new_queries && g_on) follow_queried();
	return g_on;
}

// Inject the inputs due at offset off of the current command, then flush them so the
// game's own nodes see them in this tick.
static void inject_inputs(int64_t off) {
	int due = 0;
	for (int i = 0; i < g_n_inputs && !due; i++) due = g_inputs[i].off == off;
	if (!due) return;
	int any = 0;
	Var input;
	v_obj(&input, singleton("Input"));
	Var cdb, cls;
	v_obj(&cdb, singleton("ClassDB"));
	v_text(&cls, "InputEventAction");
	for (int i = 0; i < g_n_inputs; i++) {
		if (g_inputs[i].off != off) continue;
		Var ev, rc, str, pressed;
		if (!vcall(&cdb, &sn_instantiate, (const Var *[]){&cls}, 1, &ev)) {
			v_free(&ev);
			continue;
		}
		v_float(&str, g_inputs[i].strength);
		v_bool(&pressed, g_inputs[i].strength > 0.0);
		vcall(&ev, &sn_set_action, (const Var *[]){&g_inputs[i].action}, 1, &rc);
		v_free(&rc);
		vcall(&ev, &sn_set_strength, (const Var *[]){&str}, 1, &rc);
		v_free(&rc);
		vcall(&ev, &sn_set_pressed, (const Var *[]){&pressed}, 1, &rc);
		v_free(&rc);
		vcall(&input, &sn_parse_event, (const Var *[]){&ev}, 1, &rc);
		v_free(&rc);
		v_free(&pressed);
		v_free(&str);
		v_free(&ev);
		any = 1;
	}
	if (any) {
		Var rc;
		vcall(&input, &sn_flush_events, NULL, 0, &rc);
		v_free(&rc);
	}
	v_free(&cls);
	v_free(&cdb);
	v_free(&input);
}

// ------------------------------------------------------------------ the tick
static void tick_lockstep(int64_t t) {
	if (g_left <= 0) {
		uint64_t t0 = now_us();
		send_frame(t);
		if (!g_on) return;
		g_own_us = now_us() - t0;
		Var cmd;
		if (!recv_blocking(&cmd)) {
			v_free(&cmd);
			return;
		}
		uint64_t t1 = now_us();
		int go = apply_command(&cmd, t);
		v_free(&cmd);
		if (!go) return;
		g_own_us += now_us() - t1;
	}
	inject_inputs(t - g_cmd_tick);
	g_left--;
}

static void tick_realtime(int64_t t) {
	pump_socket();
	Var cmd;
	while (g_on && next_buffered(&cmd)) {
		apply_command(&cmd, t);
		v_free(&cmd);
	}
	if (!g_on) return;
	inject_inputs(t - g_cmd_tick);
	send_heartbeat(t);
	if (g_on && t - g_last_frame_tick >= (g_obs.every > 0 ? g_obs.every : 6)) send_frame(t);
}

static void on_physics_tick(void) {
	if (!g_on || g_closing) return;
	int64_t t = physics_frames();
	g_ticks_seen++;
	if (!g_hooked) hook_events();
	if (g_realtime) tick_realtime(t);
	else tick_lockstep(t);
}

static void on_ready(Obj self) {
	if (!g_on || self != g_node) return;
	f_ptrcall(mb_get_tree, self, NULL, &g_tree);
	int64_t mode = K_PROCESS_MODE_ALWAYS, prio = -2000000000;
	GDExtensionBool on = 1;
	const void *ma[1] = {&mode};
	f_ptrcall(mb_set_process_mode, self, ma, NULL);
	const void *pa[1] = {&prio};
	f_ptrcall(mb_set_physics_priority, self, pa, NULL);
	const void *oa[1] = {&on};
	f_ptrcall(mb_set_internal_physics, self, oa, NULL);
	g_last_frame_tick = physics_frames();
	send_hello();
}

// ------------------------------------------------------------------ class glue
typedef struct {
	Obj obj;
} Instance;

static void notify(GDExtensionClassInstancePtr p, int32_t what, GDExtensionBool reversed) {
	(void)reversed;
	Instance *inst = (Instance *)p;
	if (!inst || inst->obj != g_node) return;
	switch (what) {
		case K_NOTIFICATION_READY: on_ready(inst->obj); break;
		case K_NOTIFICATION_INTERNAL_PHYSICS_PROCESS: on_physics_tick(); break;
		case K_NOTIFICATION_EXIT_TREE:
		case K_NOTIFICATION_PREDELETE: send_gone(); break;
		default: break;
	}
}

static GDExtensionObjectPtr create_instance(void *ud, GDExtensionBool notify_postinit) {
	(void)ud;
	Obj o = f_construct(&sn_node);
	Instance *inst = calloc(1, sizeof(Instance));
	inst->obj = o;
	f_set_instance(o, &g_class_name, inst);
	if (!g_node) g_node = o;
	if (notify_postinit) {
		int64_t what = K_NOTIFICATION_POSTINITIALIZE;
		GDExtensionBool rev = 0;
		const void *args[2] = {&what, &rev};
		f_ptrcall(mb_notification, o, args, NULL);
	}
	return o;
}

static void free_instance(void *ud, GDExtensionClassInstancePtr p) {
	(void)ud;
	Instance *inst = (Instance *)p;
	if (inst && inst->obj == g_node) g_node = NULL;
	free(inst);
}

// The class name: the library's file name without directory and extension, when it
// is a valid identifier.
static void class_name_from_library(char *out, size_t cap) {
	Dl_info info;
	const char *fallback = "QaTelemetryNode";
	snprintf(out, cap, "%s", fallback);
	if (!dladdr((const void *)&class_name_from_library, &info) || !info.dli_fname) return;
	const char *base = strrchr(info.dli_fname, '/');
	base = base ? base + 1 : info.dli_fname;
	size_t n = 0;
	while (base[n] && base[n] != '.' && n + 1 < cap) n++;
	if (n == 0) return;
	for (size_t i = 0; i < n; i++) {
		char c = base[i];
		int ok = (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_' || (i > 0 && c >= '0' && c <= '9');
		if (!ok) return;
	}
	memcpy(out, base, n);
	out[n] = 0;
}

static int hexval(char c) {
	if (c >= '0' && c <= '9') return c - '0';
	if (c >= 'a' && c <= 'f') return c - 'a' + 10;
	if (c >= 'A' && c <= 'F') return c - 'A' + 10;
	return -1;
}

// Read the link settings, wipe them from the environment, and connect.
static void open_link(void) {
	const char *port = getenv("QA_TELEMETRY_PORT");
	char *key = getenv("QA_TELEMETRY_KEY");
	const char *mode = getenv("QA_TELEMETRY_MODE");
	g_realtime = mode && !strcmp(mode, "realtime");
	int key_ok = key && strlen(key) == 64;
	for (int i = 0; key_ok && i < 32; i++) {
		int hi = hexval(key[2 * i]), lo = hexval(key[2 * i + 1]);
		if (hi < 0 || lo < 0) key_ok = 0;
		else g_key[i] = (uint8_t)(hi << 4 | lo);
	}
	long p = port ? strtol(port, NULL, 10) : 0;
	if (key) memset(key, 0, strlen(key));
	unsetenv("QA_TELEMETRY_KEY");
	unsetenv("QA_TELEMETRY_PORT");
	unsetenv("QA_TELEMETRY_MODE");
	if (!key_ok || p <= 0 || p > 65535) return;
	g_sock = socket(AF_INET, SOCK_STREAM, 0);
	if (g_sock < 0) return;
	int one = 1;
	setsockopt(g_sock, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
#ifdef SO_NOSIGPIPE
	setsockopt(g_sock, SOL_SOCKET, SO_NOSIGPIPE, &one, sizeof one);
#endif
	struct sockaddr_in a;
	memset(&a, 0, sizeof a);
	a.sin_family = AF_INET;
	a.sin_port = htons((uint16_t)p);
	a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	if (connect(g_sock, (struct sockaddr *)&a, sizeof a) != 0) {
		close(g_sock);
		g_sock = -1;
		return;
	}
	g_on = 1;
}

static GDExtensionMethodBindPtr method_bind(const char *cls, const char *method, GDExtensionInt hash) {
	SN c, m;
	f_sn_new(&c, cls, 0);
	f_sn_new(&m, method, 0);
	GDExtensionMethodBindPtr p = f_get_mb(&c, &m, hash);
	dtor_sname(&c);
	dtor_sname(&m);
	if (!p) g_bind_failed = 1;
	return p;
}

static void make_names(void) {
	sn_static(&sn_node, "Node");
	sn_static(&sn_entity, "entity");
	sn_static(&sn_m_id, "entity_id");
	sn_static(&sn_m_kind, "kind");
	sn_static(&sn_m_arch, "archetype");
	sn_static(&sn_m_faction, "faction");
	sn_static(&sn_m_surface, "surface");
	sn_static(&sn_m_parcel, "parcel");
	sn_static(&sn_node3d, "Node3D");
	sn_static(&sn_rigid, "RigidBody3D");
	sn_static(&sn_character, "CharacterBody3D");
	sn_static(&sn_skeleton_cls, "Skeleton3D");
	sn_static(&sn_exec, "exec");
	sn_static(&sn_keys, "keys");
	sn_static(&sn_size, "size");
	sn_static(&sn_get_node_or_null, "get_node_or_null");
	sn_static(&sn_has_signal, "has_signal");
	sn_static(&sn_connect, "connect");
	sn_static(&sn_instantiate, "instantiate");
	sn_static(&sn_set_action, "set_action");
	sn_static(&sn_set_strength, "set_strength");
	sn_static(&sn_set_pressed, "set_pressed");
	sn_static(&sn_parse_event, "parse_input_event");
	sn_static(&sn_flush_events, "flush_buffered_events");
	sn_static(&sn_find_world, "find_world_3d");
	sn_static(&sn_space_state, "get_direct_space_state");
	sn_static(&sn_set_from, "set_from");
	sn_static(&sn_set_to, "set_to");
	sn_static(&sn_set_mask, "set_collision_mask");
	sn_static(&sn_intersect_ray, "intersect_ray");
	sn_static(&sn_get, "get");
	sn_static(&sn_is_visible, "is_visible_in_tree");
	sn_static(&sn_get_children, "get_children");
	sn_static(&sn_get_fov, "get_fov");
	sn_static(&sn_get_bone_name, "get_bone_name");
	sn_static(&sn_get_skin, "get_skin");
	sn_static(&sn_get_skeleton_path, "get_skeleton_path");
	sn_static(&sn_get_mesh, "get_mesh");
	sn_static(&sn_surface_count, "get_surface_count");
	sn_static(&sn_surface_arrays, "surface_get_arrays");
	sn_static(&sn_get_path, "get_path");
	sn_static(&sn_get_version_info, "get_version_info");
	sn_static(&sn_get_setting, "get_setting");
	sn_static(&sn_get_ticks, "get_physics_ticks_per_second");
	sn_static(&sn_get_jitter, "get_physics_jitter_fix");
	sn_static(&sn_get_max_steps, "get_max_physics_steps_per_frame");
	sn_static(&sn_render_method, "get_current_rendering_method");
	sn_static(&sn_display_name, "get_name");
	sn_static(&sn_cpu_count, "get_processor_count");
	sn_static(&sn_get_env, "get_environment");
	sn_static(&sn_is_instance_valid, "is_instance_valid");
	sn_static(&sn_is_connected, "is_connected");
	sn_static(&sn_disconnect, "disconnect");
	sn_static(&sn_seat, "seat");
	sn_static(&sn_m_index, "index");
	sn_static(&sn_m_door, "door");
	sn_static(&sn_m_wheel, "wheel");
	sn_static(&sn_collision_object, "CollisionObject3D");
	sn_static(&sn_get_class, "get_class");
	static const struct {
		Var *v;
		const char *text;
	} keys[] = {
		{&k_run, "run"}, {&k_inputs, "inputs"}, {&k_dev, "dev"}, {&k_observe, "observe"},
		{&k_queries, "queries"}, {&k_quit, "quit"}, {&k_n, "n"}, {&k_census, "census"},
		{&k_meta, "meta"}, {&k_view, "view"}, {&k_bones, "bones"}, {&k_ids, "ids"},
		{&k_names, "names"}, {&k_camera, "camera"}, {&k_hud, "hud"}, {&k_state, "state"},
		{&k_every, "every"}, {&k_id, "id"}, {&k_type, "type"}, {&k_from, "from"},
		{&k_to, "to"}, {&k_mask, "mask"}, {&k_points, "points"}, {&k_y0, "y0"},
		{&k_y1, "y1"}, {&k_a, "a"}, {&k_b, "b"}, {&k_a_up, "a_up"}, {&k_b_up, "b_up"},
		{&k_entity, "entity"}, {&k_keys, "keys"}, {&k_position, "position"},
		{&k_collider, "collider"}, {&k_string, "string"}, {&k_ok, "ok"}, {&k_event, "event"},
		{&k_text, "text"}, {&k_star, "*"}, {&k_empty, ""}, {&k_skeleton_updated, "skeleton_updated"},
		{&k_seats, "seats"}, {&k_mass, "mass"}, {&k_collision_layer, "collision_layer"},
		{&k_collision_mask, "collision_mask"}, {&k_kinds, "kinds"},
	};
	for (size_t i = 0; i < sizeof keys / sizeof keys[0]; i++) v_text(keys[i].v, keys[i].text);
	v_nil(&g_pending_queries);
}

static void bind_methods(void) {
	mb_get_meta = method_bind("Object", "get_meta", H_Object_get_meta);
	mb_has_meta = method_bind("Object", "has_meta", H_Object_has_meta);
	mb_is_class = method_bind("Object", "is_class", H_Object_is_class);
	mb_notification = method_bind("Object", "notification", H_Object_notification);
	mb_get_tree = method_bind("Node", "get_tree", H_Node_get_tree);
	mb_get_index = method_bind("Node", "get_index", H_Node_get_index);
	mb_set_internal_physics = method_bind("Node", "set_physics_process_internal", H_Node_set_physics_process_internal);
	mb_set_physics_priority = method_bind("Node", "set_physics_process_priority", H_Node_set_physics_process_priority);
	mb_set_process_mode = method_bind("Node", "set_process_mode", H_Node_set_process_mode);
	mb_find_children = method_bind("Node", "find_children", H_Node_find_children);
	mb_get_parent = method_bind("Node", "get_parent", H_Node_get_parent);
	mb_is_in_group = method_bind("Node", "is_in_group", H_Node_is_in_group);
	mb_get_viewport = method_bind("Node", "get_viewport", H_Node_get_viewport);
	mb_nodes_in_group = method_bind("SceneTree", "get_nodes_in_group", H_SceneTree_get_nodes_in_group);
	mb_get_root = method_bind("SceneTree", "get_root", H_SceneTree_get_root);
	mb_quit = method_bind("SceneTree", "quit", H_SceneTree_quit);
	mb_global_transform = method_bind("Node3D", "get_global_transform", H_Node3D_get_global_transform);
	mb_find_bone = method_bind("Skeleton3D", "find_bone", H_Skeleton3D_find_bone);
	mb_bone_global_pose = method_bind("Skeleton3D", "get_bone_global_pose", H_Skeleton3D_get_bone_global_pose);
	mb_bone_count = method_bind("Skeleton3D", "get_bone_count", H_Skeleton3D_get_bone_count);
	mb_linear_velocity = method_bind("RigidBody3D", "get_linear_velocity", H_RigidBody3D_get_linear_velocity);
	mb_real_velocity = method_bind("CharacterBody3D", "get_real_velocity", H_CharacterBody3D_get_real_velocity);
	mb_physics_frames = method_bind("Engine", "get_physics_frames", H_Engine_get_physics_frames);
	mb_camera_3d = method_bind("Viewport", "get_camera_3d", H_Viewport_get_camera_3d);
	mb_in_frustum = method_bind("Camera3D", "is_position_in_frustum", H_Camera3D_is_position_in_frustum);
	mb_parse_json = method_bind("JSON", "parse_string", H_JSON_parse_string);
	SN m;
	f_sn_new(&m, "size", 0);
	bm_array_size = f_builtin(GDEXTENSION_VARIANT_TYPE_ARRAY, &m, HB_Array_size);
	dtor_sname(&m);
	if (!bm_array_size) g_bind_failed = 1;
}

static void initialize(void *ud, GDExtensionInitializationLevel level) {
	(void)ud;
	if (level != GDEXTENSION_INITIALIZATION_SCENE) return;
	for (int t = 1; t < T_MAX; t++) {
		vfrom[t] = f_from_type((GDExtensionVariantType)t);
		vto[t] = f_to_type((GDExtensionVariantType)t);
	}
	ctor_array = f_ctor(GDEXTENSION_VARIANT_TYPE_ARRAY, 0);
	ctor_string = f_ctor(GDEXTENSION_VARIANT_TYPE_STRING, 0);
	dtor_array = f_dtor(GDEXTENSION_VARIANT_TYPE_ARRAY);
	dtor_string = f_dtor(GDEXTENSION_VARIANT_TYPE_STRING);
	dtor_sname = f_dtor(GDEXTENSION_VARIANT_TYPE_STRING_NAME);
	dtor_callable = f_dtor(GDEXTENSION_VARIANT_TYPE_CALLABLE);
	jb_init(&g_frame, FRAME_LIMIT);
	jb_init(&g_dev, DEV_LIMIT);
	jb_init(&g_events, EVENTS_LIMIT);
	make_names();
	bind_methods();
	open_link();
	if (g_bind_failed && g_on) {
		fprintf(stderr, "qa telemetry: engine version mismatch\n");
		close(g_sock);
		g_sock = -1;
		g_on = 0;
	}
	// The class exists only in processes the kit starts (link settings present). The
	// editor that runs a headless import never sees it: in 4.7.2 an exposed extension
	// class referenced by a project scene crashes the editor while it loads its docks,
	// and an unexposed class cannot be instantiated from the autoload scene.
	if (!g_on) return;
	char name[64];
	class_name_from_library(name, sizeof name);
	f_sn_new(&g_class_name, name, 0);
	GDExtensionClassCreationInfo6 ci;
	memset(&ci, 0, sizeof ci);
	ci.is_exposed = 1;
	ci.notification_func = notify;
	ci.create_instance_func = create_instance;
	ci.free_instance_func = free_instance;
	f_reg_class(g_lib, &g_class_name, &sn_node, &ci);
}

static void deinitialize(void *ud, GDExtensionInitializationLevel level) {
	(void)ud;
	if (level != GDEXTENSION_INITIALIZATION_SCENE) return;
	if (g_sock >= 0) close(g_sock);
	g_sock = -1;
	g_on = 0;
}

// The cast goes through void (*)(void), which compilers let any function pointer type be
// cast to and from; -Wextra warns about a direct cast from the interface's void (*)().
#define LOAD(var, name)                                   \
	do {                                                  \
		var = (__typeof__(var))(void (*)(void))gpa(name); \
		if (!var) return 0;                               \
	} while (0)

EXPORT GDExtensionBool qa_telemetry_init(GDExtensionInterfaceGetProcAddress gpa,
		GDExtensionClassLibraryPtr lib, GDExtensionInitialization *r_init) {
	g_lib = lib;
	LOAD(f_sn_new, "string_name_new_with_latin1_chars");
	LOAD(f_str_new, "string_new_with_utf8_chars_and_len2");
	LOAD(f_str_utf8, "string_to_utf8_chars");
	LOAD(f_v_nil, "variant_new_nil");
	LOAD(f_v_copy, "variant_new_copy");
	LOAD(f_v_destroy, "variant_destroy");
	LOAD(f_v_type, "variant_get_type");
	LOAD(f_v_call, "variant_call");
	LOAD(f_v_get, "variant_get");
	LOAD(f_v_get_indexed, "variant_get_indexed");
	LOAD(f_v_stringify, "variant_stringify");
	LOAD(f_v_construct, "variant_construct");
	LOAD(f_v_obj_id, "variant_get_object_instance_id");
	LOAD(f_from_type, "get_variant_from_type_constructor");
	LOAD(f_to_type, "get_variant_to_type_constructor");
	LOAD(f_ctor, "variant_get_ptr_constructor");
	LOAD(f_dtor, "variant_get_ptr_destructor");
	LOAD(f_builtin, "variant_get_ptr_builtin_method");
	LOAD(f_arr_at, "array_operator_index_const");
	LOAD(f_ptrcall, "object_method_bind_ptrcall");
	LOAD(f_get_mb, "classdb_get_method_bind");
	LOAD(f_construct, "classdb_construct_object3");
	LOAD(f_reg_class, "classdb_register_extension_class6");
	LOAD(f_set_instance, "object_set_instance");
	LOAD(f_instance_id, "object_get_instance_id");
	LOAD(f_from_id, "object_get_instance_from_id");
	LOAD(f_singleton, "global_get_singleton");
	LOAD(f_callable_new, "callable_custom_create2");
	r_init->minimum_initialization_level = GDEXTENSION_INITIALIZATION_SCENE;
	r_init->userdata = NULL;
	r_init->initialize = initialize;
	r_init->deinitialize = deinitialize;
	return 1;
}
