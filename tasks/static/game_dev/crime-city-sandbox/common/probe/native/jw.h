// A growable byte buffer with JSON writing helpers, for the telemetry frames.
// No engine dependency. A buffer stops growing at its limit and remembers that it
// overflowed; the caller then sends a short overflow notice instead of the frame.
#pragma once
#include <stddef.h>
#include <stdint.h>

typedef struct {
	char *p;       // bytes written so far (not NUL-terminated)
	size_t n;      // number of bytes in p
	size_t cap;    // allocated size of p
	size_t limit;  // largest size the buffer may reach
	int over;      // 1 once a write was dropped because of the limit or allocation
} jbuf;

// Set up an empty buffer that may grow to limit bytes. Allocation is lazy.
void jb_init(jbuf *b, size_t limit);

// Release the memory of b and leave it empty (it can be reused after jb_init).
void jb_free(jbuf *b);

// Forget the contents of b (keeps its allocation and limit, clears the overflow flag).
void jb_clear(jbuf *b);

// Append n raw bytes.
void jb_raw(jbuf *b, const char *s, size_t n);

// Append a NUL-terminated literal, unescaped (for JSON punctuation and known keys).
void jb_lit(jbuf *b, const char *s);

// Append s (n bytes of UTF-8) as a quoted, escaped JSON string.
void jb_str(jbuf *b, const char *s, size_t n);

// Append a NUL-terminated string as a quoted, escaped JSON string.
void jb_cstr(jbuf *b, const char *s);

// Append a JSON integer.
void jb_i64(jbuf *b, int64_t v);

// Append a JSON number for a double: the shortest form that round-trips (up to 17
// significant digits), always with a fraction or exponent so it reads back as a
// float; NaN and infinities are written as null. Independent of the C locale.
void jb_f64(jbuf *b, double v);

// Append true or false.
void jb_bool(jbuf *b, int v);

// Append "[x,y,z]" from three floats.
void jb_vec3(jbuf *b, float x, float y, float z);
