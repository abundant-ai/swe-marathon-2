# Reconstruct episode links from the recorder journal

The episode table alone cannot tell us who owns a plausible looking clip. We have a separate journal from the capture process that records which episodes committed and identifies selected decoded camera frames. Add a repair plan that uses the journal and the original frame rows. Keep the audit working.

```bash
python3 -m lerobot_repair plan --dataset DATASET --ledger LEDGER.json --output PLAN.json
```

The ledger is JSON with schema_version 1 and episodes. Each entry has a distinct nonnegative integer episode_index, Boolean committed and cameras object keyed by camera name. A camera entry is a list of anchors. Each anchor contains a distinct nonnegative episode-local frame and a lowercase SHA-256 hex digest sha256. Hash the exact contiguous RGB24 bytes of the decoded frame in row-major order, with no dimensions or timestamp in the hash. A multi-frame episode needs at least two anchors per camera. A one-frame episode needs one. Missing evidence, too few anchors or a frame index beyond the episode is insufficient evidence. Invalid anchor shapes, duplicate frame keys and malformed digests make the ledger malformed.

Include every episode ID found in the data, episode metadata or ledger. If the ledger did not commit an episode, quarantine it with UNCOMMITTED. If a committed episode has missing or invalid frame rows, quarantine it with INVALID_FRAME_ROWS. For an otherwise usable episode, search each camera's decodable fixed-rate MP4 files for every in-bounds window of the episode's length whose frames satisfy all anchors. Missing or insufficient anchors yield NO_EVIDENCE/CAMERA. No matched window yields NO_CLIP/CAMERA. Several matches yield AMBIGUOUS_CLIP/CAMERA. The old metadata is never evidence of ownership. Among episodes with one independently matched clip for every camera, quarantine all episodes with pairwise overlapping claims on the same camera file. Record CLIP_CONFLICT/CAMERA for each conflicting camera. Touching intervals do not overlap.

Write a JSON object with schema_version 1, source_sha256, ledger_sha256 and episodes. The source fingerprint is SHA-256 of UTF-8 records, one per native dataset file under data, meta, or videos. Sort by relative POSIX path. A record is path, a single tab, SHA-256 hex of that file's exact bytes, and a newline. Include every regular file below those directories. Refuse symbolic links there. ledger_sha256 hashes the exact ledger bytes.

Each plan entry has episode_index, status keep or quarantine, sorted reasons and a videos object. Kept episodes have no reasons and a video entry for each camera. Each video entry is [chunk_index,file_index,first_frame,past_last_frame]. Quarantined episodes have an empty videos object. Sort by episode_index. A change in original metadata does not by itself justify discarding a recoverable episode. Do not modify the dataset or the journal. Reject malformed input and preserve existing output as before.
