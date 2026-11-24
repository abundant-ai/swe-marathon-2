# Release, pin and roll back a map

Operators want to inspect proposed changes before making a new map active. A localization run must be able to pin a version and reproduce its inputs after a later update or rollback. Add local storage for immutable snapshots. Keep the mapping, registration and proposal interfaces working.

```bash
python3 -m versioned_mapping init --store STORE --map MAP.json
python3 -m versioned_mapping publish --store STORE --base VERSION --patch PATCH.json
python3 -m versioned_mapping activate --store STORE --version VERSION --expect-active VERSION
python3 -m versioned_mapping snapshot --store STORE --version VERSION --output MAP.json
```

A version ID is the lowercase SHA-256 of the exact bytes of its map snapshot. Each of the first three commands writes a JSON object with `version` and `active_version` to stdout on success.

- `init` starts a store at a new path. Preserve the original map bytes and set its version active.
- `publish` builds a snapshot from the specified base while keeping the current active version. Validate the base hash, cell bounds, that each cell is changed at most once, that each `from` agrees with the base, that `to` differs from `from`, and that each change has at least two distinct nonempty supporting visit IDs. Repeating a publication returns the same version. An empty patch returns the base version.
- `activate` switches to any stored version, including an older one. Change the active pointer only if it still equals `--expect-active`. If competing writers use the same expected version and request distinct new versions, only one may change it.
- `snapshot` exports the exact stored bytes. The special value `active` resolves the active version as of this read. Supplying an ID pins that version regardless of later promotion or rollback.

Reject invalid operations with a nonzero exit. Preserve existing snapshots and the active pointer if validation fails. Readers should see a complete old or new version during promotion. Pinned versions must still be readable after repeated publications and changes to the active version.
