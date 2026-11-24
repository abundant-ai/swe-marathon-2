# Separate layout changes from passing traffic

We have several registered follow-up visits. A temporary obstruction in one run should leave the released map alone. The proposed update needs to explain which independent visits support each changed cell. Protected structural cells stay as they were.

Keep both preceding commands and add a read-only proposal command.

```bash
python3 -m versioned_mapping propose --base MAP.json --evidence EVIDENCE.json --output PATCH.json
```

The evidence file contains `visits` and `protected_cells` arrays. Each visit entry has `visit`, a path to the earlier JSON format resolved relative to the evidence file, and a finite `world_from_visit: [x,y,yaw]` from registration. Visit IDs must be unique. Each protected cell is a valid `[column,row]` in the base grid.

Use the same ray geometry as `build`. For this command, a visit supports a free or occupied state only when it has evidence for that state and no evidence for the opposite state in that cell. Mixed observations within one visit abstain. Propose a state change only when at least two distinct visits support the new state, no visit supports the opposite state, and the cell is unprotected. Unknown and unseen cells supply no vote.

Write a JSON object with `schema_version: 1`, `base_sha256` of the exact base map file bytes, and a `changes` array in row-major order. Each entry contains `cell: [column,row]`, `from` and `to` states and `support`, the lexicographically sorted list of all visit IDs that support `to`. A missing base cell has state `unknown`. The target is either `free` or `occupied`.

Write the same bytes if only the order of the input visits changes. Leave the base map untouched. Reject invalid evidence and leave the destination intact.
