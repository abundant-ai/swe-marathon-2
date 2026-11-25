// Native half of the QA probe (Phase 0 proof). Plain C against the gdextension_interface.h
// dumped from the pinned Godot binary (no godot-cpp). It registers one class whose methods
// hold the per-run key and the harness socket in native memory:
//   connect_harness() -> bool   reads QA_PROBE_PORT / QA_PROBE_KEY, removes the key from the
//                               environment, connects to 127.0.0.1:port
//   send(payload: String) -> bool   frames and signs one message (HMAC-SHA256)
//   recv() -> String                blocks for one message, verifies it, "" on failure
// The class name comes from QA_PROBE_CLASS (random per run), default "QaCore".
#include <arpa/inet.h>
#include <netinet/in.h>
#include <netinet/tcp.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/socket.h>
#include <unistd.h>

#include "gen/gdextension_interface.h"

typedef struct { uint8_t opaque[8]; } SN;    // StringName storage
typedef struct { uint8_t opaque[8]; } STR;   // String storage

static GDExtensionClassLibraryPtr g_lib;
static GDExtensionInterfaceStringNameNewWithLatin1Chars sn_new;
static GDExtensionInterfaceStringNewWithUtf8CharsAndLen2 str_new;
static GDExtensionInterfaceStringToUtf8Chars str_to_utf8;
static GDExtensionInterfaceClassdbConstructObject3 construct3;
static GDExtensionInterfaceObjectSetInstance set_instance;
static GDExtensionInterfaceClassdbRegisterExtensionClass6 reg_class;
static GDExtensionInterfaceClassdbRegisterExtensionClassMethod reg_method;
static GDExtensionInterfaceGetVariantFromTypeConstructor var_from_type;
static GDExtensionInterfaceGetVariantToTypeConstructor var_to_type;
static GDExtensionInterfaceVariantGetPtrDestructor get_dtor;

static SN class_name, parent_name, empty_sn;
static STR empty_str;
static uint8_t g_key[32];
static int g_key_len = 0;
static int g_sock = -1;

// ---------------------------------------------------------------- SHA-256 / HMAC
typedef struct { uint32_t h[8]; uint64_t len; uint8_t buf[64]; size_t n; } sha256_t;
static const uint32_t K[64] = {
	0x428a2f98, 0x71374491, 0xb5c0fbcf, 0xe9b5dba5, 0x3956c25b, 0x59f111f1, 0x923f82a4, 0xab1c5ed5,
	0xd807aa98, 0x12835b01, 0x243185be, 0x550c7dc3, 0x72be5d74, 0x80deb1fe, 0x9bdc06a7, 0xc19bf174,
	0xe49b69c1, 0xefbe4786, 0x0fc19dc6, 0x240ca1cc, 0x2de92c6f, 0x4a7484aa, 0x5cb0a9dc, 0x76f988da,
	0x983e5152, 0xa831c66d, 0xb00327c8, 0xbf597fc7, 0xc6e00bf3, 0xd5a79147, 0x06ca6351, 0x14292967,
	0x27b70a85, 0x2e1b2138, 0x4d2c6dfc, 0x53380d13, 0x650a7354, 0x766a0abb, 0x81c2c92e, 0x92722c85,
	0xa2bfe8a1, 0xa81a664b, 0xc24b8b70, 0xc76c51a3, 0xd192e819, 0xd6990624, 0xf40e3585, 0x106aa070,
	0x19a4c116, 0x1e376c08, 0x2748774c, 0x34b0bcb5, 0x391c0cb3, 0x4ed8aa4a, 0x5b9cca4f, 0x682e6ff3,
	0x748f82ee, 0x78a5636f, 0x84c87814, 0x8cc70208, 0x90befffa, 0xa4506ceb, 0xbef9a3f7, 0xc67178f2};
#define ROR(x, n) (((x) >> (n)) | ((x) << (32 - (n))))
static void sha_block(sha256_t *s, const uint8_t *p) {
	uint32_t w[64], a, b, c, d, e, f, g, h;
	for (int i = 0; i < 16; i++) w[i] = (uint32_t)p[4 * i] << 24 | (uint32_t)p[4 * i + 1] << 16 | (uint32_t)p[4 * i + 2] << 8 | p[4 * i + 3];
	for (int i = 16; i < 64; i++) {
		uint32_t s0 = ROR(w[i - 15], 7) ^ ROR(w[i - 15], 18) ^ (w[i - 15] >> 3);
		uint32_t s1 = ROR(w[i - 2], 17) ^ ROR(w[i - 2], 19) ^ (w[i - 2] >> 10);
		w[i] = w[i - 16] + s0 + w[i - 7] + s1;
	}
	a = s->h[0]; b = s->h[1]; c = s->h[2]; d = s->h[3]; e = s->h[4]; f = s->h[5]; g = s->h[6]; h = s->h[7];
	for (int i = 0; i < 64; i++) {
		uint32_t t1 = h + (ROR(e, 6) ^ ROR(e, 11) ^ ROR(e, 25)) + ((e & f) ^ (~e & g)) + K[i] + w[i];
		uint32_t t2 = (ROR(a, 2) ^ ROR(a, 13) ^ ROR(a, 22)) + ((a & b) ^ (a & c) ^ (b & c));
		h = g; g = f; f = e; e = d + t1; d = c; c = b; b = a; a = t1 + t2;
	}
	s->h[0] += a; s->h[1] += b; s->h[2] += c; s->h[3] += d; s->h[4] += e; s->h[5] += f; s->h[6] += g; s->h[7] += h;
}
static void sha_init(sha256_t *s) {
	static const uint32_t iv[8] = {0x6a09e667, 0xbb67ae85, 0x3c6ef372, 0xa54ff53a, 0x510e527f, 0x9b05688c, 0x1f83d9ab, 0x5be0cd19};
	memcpy(s->h, iv, sizeof iv); s->len = 0; s->n = 0;
}
static void sha_update(sha256_t *s, const uint8_t *p, size_t n) {
	s->len += n;
	while (n > 0) {
		size_t k = 64 - s->n < n ? 64 - s->n : n;
		memcpy(s->buf + s->n, p, k); s->n += k; p += k; n -= k;
		if (s->n == 64) { sha_block(s, s->buf); s->n = 0; }
	}
}
static void sha_final(sha256_t *s, uint8_t out[32]) {
	uint64_t bits = s->len * 8;
	uint8_t pad = 0x80, zero = 0;
	sha_update(s, &pad, 1);
	while (s->n != 56) sha_update(s, &zero, 1);
	uint8_t lb[8];
	for (int i = 0; i < 8; i++) lb[i] = (uint8_t)(bits >> (56 - 8 * i));
	sha_update(s, lb, 8);
	for (int i = 0; i < 8; i++) { out[4 * i] = s->h[i] >> 24; out[4 * i + 1] = s->h[i] >> 16; out[4 * i + 2] = s->h[i] >> 8; out[4 * i + 3] = s->h[i]; }
}
static void hmac(const uint8_t *msg, size_t n, uint8_t out[32]) {
	uint8_t k[64] = {0}, ip[64], op[64], inner[32];
	memcpy(k, g_key, g_key_len);
	for (int i = 0; i < 64; i++) { ip[i] = k[i] ^ 0x36; op[i] = k[i] ^ 0x5c; }
	sha256_t s;
	sha_init(&s); sha_update(&s, ip, 64); sha_update(&s, msg, n); sha_final(&s, inner);
	sha_init(&s); sha_update(&s, op, 64); sha_update(&s, inner, 32); sha_final(&s, out);
}

// ---------------------------------------------------------------- socket I/O
static int read_exact(uint8_t *p, size_t n) {
	while (n > 0) {
		ssize_t r = recv(g_sock, p, n, 0);
		if (r <= 0) return 0;
		p += r; n -= (size_t)r;
	}
	return 1;
}
static int write_all(const uint8_t *p, size_t n) {
	while (n > 0) {
		ssize_t r = send(g_sock, p, n, 0);
		if (r <= 0) return 0;
		p += r; n -= (size_t)r;
	}
	return 1;
}
static int do_connect(void) {
	const char *port = getenv("QA_PROBE_PORT");
	const char *key = getenv("QA_PROBE_KEY");
	if (!port || !key) return 0;
	size_t kl = strlen(key) / 2;
	if (kl > 32) kl = 32;
	for (size_t i = 0; i < kl; i++) { unsigned v; sscanf(key + 2 * i, "%2x", &v); g_key[i] = (uint8_t)v; }
	g_key_len = (int)kl;
	memset((char *)key, 0, strlen(key));   // wipe the environment copy, then drop the variable
	unsetenv("QA_PROBE_KEY");
	g_sock = socket(AF_INET, SOCK_STREAM, 0);
	struct sockaddr_in a = {0};
	a.sin_family = AF_INET; a.sin_port = htons((uint16_t)atoi(port)); a.sin_addr.s_addr = htonl(INADDR_LOOPBACK);
	if (connect(g_sock, (struct sockaddr *)&a, sizeof a) != 0) return 0;
	int one = 1;
	setsockopt(g_sock, IPPROTO_TCP, TCP_NODELAY, &one, sizeof one);
	return 1;
}
static int do_send(const STR *s) {
	GDExtensionInt n = str_to_utf8(s, NULL, 0);
	uint8_t *buf = malloc((size_t)n + 36);
	str_to_utf8(s, (char *)buf + 36, n);
	uint32_t total = (uint32_t)n + 32;
	buf[0] = total >> 24; buf[1] = total >> 16; buf[2] = total >> 8; buf[3] = total;
	hmac(buf + 36, (size_t)n, buf + 4);
	int ok = write_all(buf, (size_t)n + 36);
	free(buf);
	return ok;
}
static void do_recv(STR *r_ret) {
	uint8_t hdr[4];
	if (g_sock < 0 || !read_exact(hdr, 4)) { str_new(r_ret, "", 0); return; }
	uint32_t n = (uint32_t)hdr[0] << 24 | (uint32_t)hdr[1] << 16 | (uint32_t)hdr[2] << 8 | hdr[3];
	if (n < 32 || n > (64u << 20)) { str_new(r_ret, "", 0); return; }
	uint8_t *buf = malloc(n);
	uint8_t mac[32];
	if (!read_exact(buf, n)) { free(buf); str_new(r_ret, "", 0); return; }
	hmac(buf + 32, n - 32, mac);
	uint8_t diff = 0;
	for (int i = 0; i < 32; i++) diff |= mac[i] ^ buf[i];
	if (diff) str_new(r_ret, "", 0);
	else str_new(r_ret, (const char *)buf + 32, n - 32);
	free(buf);
}

// ---------------------------------------------------------------- class glue
static GDExtensionObjectPtr create_instance(void *ud, GDExtensionBool notify) {
	(void)ud; (void)notify;
	GDExtensionObjectPtr obj = construct3(&parent_name);
	set_instance(obj, &class_name, (GDExtensionClassInstancePtr)1);
	return obj;
}
static void free_instance(void *ud, GDExtensionClassInstancePtr inst) { (void)ud; (void)inst; }

enum { M_CONNECT, M_SEND, M_RECV };

static void ptrcall(void *ud, GDExtensionClassInstancePtr inst, const GDExtensionConstTypePtr *args, GDExtensionTypePtr r_ret) {
	(void)inst;
	switch ((intptr_t)ud) {
		case M_CONNECT: *(GDExtensionBool *)r_ret = (GDExtensionBool)do_connect(); break;
		case M_SEND: *(GDExtensionBool *)r_ret = (GDExtensionBool)do_send((const STR *)args[0]); break;
		case M_RECV: do_recv((STR *)r_ret); break;
	}
}
static void call(void *ud, GDExtensionClassInstancePtr inst, const GDExtensionConstVariantPtr *args, GDExtensionInt argc,
		GDExtensionVariantPtr r_ret, GDExtensionCallError *err) {
	(void)inst; (void)argc;
	err->error = GDEXTENSION_CALL_OK;
	switch ((intptr_t)ud) {
		case M_CONNECT: { GDExtensionBool b = (GDExtensionBool)do_connect(); var_from_type(GDEXTENSION_VARIANT_TYPE_BOOL)(r_ret, &b); break; }
		case M_SEND: {
			STR s;
			var_to_type(GDEXTENSION_VARIANT_TYPE_STRING)(&s, (GDExtensionVariantPtr)args[0]);
			GDExtensionBool b = (GDExtensionBool)do_send(&s);
			get_dtor(GDEXTENSION_VARIANT_TYPE_STRING)(&s);
			var_from_type(GDEXTENSION_VARIANT_TYPE_BOOL)(r_ret, &b);
			break;
		}
		case M_RECV: {
			STR s;
			do_recv(&s);
			var_from_type(GDEXTENSION_VARIANT_TYPE_STRING)(r_ret, &s);
			get_dtor(GDEXTENSION_VARIANT_TYPE_STRING)(&s);
			break;
		}
	}
}

static void add_method(const char *name, intptr_t id, GDExtensionVariantType ret, int nargs) {
	SN mname;
	sn_new(&mname, name, 0);
	GDExtensionPropertyInfo rinfo = {ret, &empty_sn, &empty_sn, 0, &empty_str, 6};
	SN aname;
	sn_new(&aname, "payload", 0);
	GDExtensionPropertyInfo ainfo = {GDEXTENSION_VARIANT_TYPE_STRING, &aname, &empty_sn, 0, &empty_str, 6};
	GDExtensionClassMethodArgumentMetadata ameta = GDEXTENSION_METHOD_ARGUMENT_METADATA_NONE;
	GDExtensionClassMethodInfo mi = {0};
	mi.name = &mname;
	mi.method_userdata = (void *)id;
	mi.call_func = call;
	mi.ptrcall_func = ptrcall;
	mi.method_flags = GDEXTENSION_METHOD_FLAG_NORMAL;
	mi.has_return_value = 1;
	mi.return_value_info = &rinfo;
	mi.return_value_metadata = GDEXTENSION_METHOD_ARGUMENT_METADATA_NONE;
	mi.argument_count = (uint32_t)nargs;
	mi.arguments_info = nargs ? &ainfo : NULL;
	mi.arguments_metadata = nargs ? &ameta : NULL;
	reg_method(g_lib, &class_name, &mi);
}

static void initialize(void *ud, GDExtensionInitializationLevel level) {
	(void)ud;
	if (level != GDEXTENSION_INITIALIZATION_SCENE) return;
	const char *cn = getenv("QA_PROBE_CLASS");
	sn_new(&class_name, cn && *cn ? cn : "QaCore", 0);
	sn_new(&parent_name, "Object", 0);
	sn_new(&empty_sn, "", 0);
	str_new(&empty_str, "", 0);
	GDExtensionClassCreationInfo6 ci = {0};
	ci.is_exposed = 1;
	ci.create_instance_func = create_instance;
	ci.free_instance_func = free_instance;
	reg_class(g_lib, &class_name, &parent_name, &ci);
	add_method("connect_harness", M_CONNECT, GDEXTENSION_VARIANT_TYPE_BOOL, 0);
	add_method("send", M_SEND, GDEXTENSION_VARIANT_TYPE_BOOL, 1);
	add_method("recv", M_RECV, GDEXTENSION_VARIANT_TYPE_STRING, 0);
}
static void deinitialize(void *ud, GDExtensionInitializationLevel level) { (void)ud; (void)level; }

__attribute__((visibility("default")))
GDExtensionBool qa_core_init(GDExtensionInterfaceGetProcAddress gpa, GDExtensionClassLibraryPtr lib, GDExtensionInitialization *r_init) {
	g_lib = lib;
	sn_new = (GDExtensionInterfaceStringNameNewWithLatin1Chars)gpa("string_name_new_with_latin1_chars");
	str_new = (GDExtensionInterfaceStringNewWithUtf8CharsAndLen2)gpa("string_new_with_utf8_chars_and_len2");
	str_to_utf8 = (GDExtensionInterfaceStringToUtf8Chars)gpa("string_to_utf8_chars");
	construct3 = (GDExtensionInterfaceClassdbConstructObject3)gpa("classdb_construct_object3");
	set_instance = (GDExtensionInterfaceObjectSetInstance)gpa("object_set_instance");
	reg_class = (GDExtensionInterfaceClassdbRegisterExtensionClass6)gpa("classdb_register_extension_class6");
	reg_method = (GDExtensionInterfaceClassdbRegisterExtensionClassMethod)gpa("classdb_register_extension_class_method");
	var_from_type = (GDExtensionInterfaceGetVariantFromTypeConstructor)gpa("get_variant_from_type_constructor");
	var_to_type = (GDExtensionInterfaceGetVariantToTypeConstructor)gpa("get_variant_to_type_constructor");
	get_dtor = (GDExtensionInterfaceVariantGetPtrDestructor)gpa("variant_get_ptr_destructor");
	if (!sn_new || !str_new || !str_to_utf8 || !construct3 || !set_instance || !reg_class || !reg_method ||
			!var_from_type || !var_to_type || !get_dtor)
		return 0;
	r_init->minimum_initialization_level = GDEXTENSION_INITIALIZATION_SCENE;
	r_init->userdata = NULL;
	r_init->initialize = initialize;
	r_init->deinitialize = deinitialize;
	return 1;
}
