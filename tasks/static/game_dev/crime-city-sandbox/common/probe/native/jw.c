// JSON writing helpers (see jw.h for the contracts).
#include "jw.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

void jb_init(jbuf *b, size_t limit) {
	b->p = NULL;
	b->n = 0;
	b->cap = 0;
	b->limit = limit;
	b->over = 0;
}

void jb_free(jbuf *b) {
	free(b->p);
	b->p = NULL;
	b->n = 0;
	b->cap = 0;
	b->over = 0;
}

void jb_clear(jbuf *b) {
	b->n = 0;
	b->over = 0;
}

// Make room for k more bytes; returns 0 (and marks overflow) when that is not possible.
static int reserve(jbuf *b, size_t k) {
	if (b->over) return 0;
	if (b->n + k > b->limit) {
		b->over = 1;
		return 0;
	}
	if (b->n + k <= b->cap) return 1;
	size_t cap = b->cap ? b->cap : 4096;
	while (cap < b->n + k) cap *= 2;
	if (cap > b->limit) cap = b->limit;
	char *p = realloc(b->p, cap);
	if (!p) {
		b->over = 1;
		return 0;
	}
	b->p = p;
	b->cap = cap;
	return 1;
}

void jb_raw(jbuf *b, const char *s, size_t n) {
	if (n == 0 || !reserve(b, n)) return;
	memcpy(b->p + b->n, s, n);
	b->n += n;
}

void jb_lit(jbuf *b, const char *s) { jb_raw(b, s, strlen(s)); }

void jb_str(jbuf *b, const char *s, size_t n) {
	static const char hex[] = "0123456789abcdef";
	jb_raw(b, "\"", 1);
	size_t start = 0;
	for (size_t i = 0; i < n; i++) {
		unsigned char c = (unsigned char)s[i];
		if (c >= 0x20 && c != '"' && c != '\\') continue;
		jb_raw(b, s + start, i - start);
		if (c == '"') jb_raw(b, "\\\"", 2);
		else if (c == '\\') jb_raw(b, "\\\\", 2);
		else if (c == '\n') jb_raw(b, "\\n", 2);
		else if (c == '\t') jb_raw(b, "\\t", 2);
		else if (c == '\r') jb_raw(b, "\\r", 2);
		else {
			char u[6] = {'\\', 'u', '0', '0', hex[c >> 4], hex[c & 15]};
			jb_raw(b, u, 6);
		}
		start = i + 1;
	}
	jb_raw(b, s + start, n - start);
	jb_raw(b, "\"", 1);
}

void jb_cstr(jbuf *b, const char *s) { jb_str(b, s, strlen(s)); }

void jb_i64(jbuf *b, int64_t v) {
	char t[32];
	int k = snprintf(t, sizeof t, "%lld", (long long)v);
	jb_raw(b, t, (size_t)k);
}

void jb_f64(jbuf *b, double v) {
	if (isnan(v) || isinf(v)) {
		jb_raw(b, "null", 4);
		return;
	}
	char t[40];
	int k = 0;
	// The shortest of %.9g ... %.17g that reads back to the same double.
	for (int prec = 9; prec <= 17; prec++) {
		k = snprintf(t, sizeof t, "%.*g", prec, v);
		for (int i = 0; i < k; i++) {
			if (t[i] == ',') t[i] = '.';  // a decimal comma from the C locale
		}
		if (strtod(t, NULL) == v) break;
	}
	int has_point = 0;
	for (int i = 0; i < k; i++) {
		if (t[i] == '.' || t[i] == 'e' || t[i] == 'E') has_point = 1;
	}
	jb_raw(b, t, (size_t)k);
	if (!has_point) jb_raw(b, ".0", 2);
}

void jb_bool(jbuf *b, int v) { jb_lit(b, v ? "true" : "false"); }

void jb_vec3(jbuf *b, float x, float y, float z) {
	jb_raw(b, "[", 1);
	jb_f64(b, x);
	jb_raw(b, ",", 1);
	jb_f64(b, y);
	jb_raw(b, ",", 1);
	jb_f64(b, z);
	jb_raw(b, "]", 1);
}
