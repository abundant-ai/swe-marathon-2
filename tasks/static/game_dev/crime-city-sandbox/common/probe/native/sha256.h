// SHA-256 and HMAC-SHA256 for the QA telemetry link (FIPS 180-4, RFC 2104).
// Plain C, no engine dependency, so the link's signing can be checked on its own.
#pragma once
#include <stddef.h>
#include <stdint.h>

typedef struct {
	uint32_t h[8];
	uint64_t len;
	uint8_t buf[64];
	size_t n;
} sha256_ctx;

// Start a digest. Must be called before sha256_update on a fresh or reused context.
void sha256_init(sha256_ctx *s);

// Feed n bytes at p into the digest. p may be NULL only when n is 0.
void sha256_update(sha256_ctx *s, const uint8_t *p, size_t n);

// Finish the digest and write the 32-byte result to out. The context must be
// re-initialised before reuse.
void sha256_final(sha256_ctx *s, uint8_t out[32]);

// HMAC-SHA256 of msg (n bytes) under key (key_len bytes, at most 64), written to out.
// Keys longer than 64 bytes are not supported (the link uses 32-byte keys).
void hmac_sha256(const uint8_t *key, size_t key_len, const uint8_t *msg, size_t n, uint8_t out[32]);

// Constant-time check that two 32-byte tags are equal; returns 1 when they are, else 0.
int tag_equal(const uint8_t a[32], const uint8_t b[32]);
