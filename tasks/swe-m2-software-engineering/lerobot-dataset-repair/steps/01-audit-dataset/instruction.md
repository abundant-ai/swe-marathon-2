# Audit a LeRobot dataset before training

We record demonstrations into LeRobotDataset v3.0. An interrupted recording or a stale episode table can leave the Parquet data and camera videos readable while training samples pair actions with the wrong frames. I need an offline audit that identifies the affected episodes without modifying the recording.

Build a modular Python package in /app/lerobot_repair. PyArrow, NumPy and PyAV are available. This work uses a local, fixed-frame-rate subset of v3.0 with native Parquet frame and episode tables and RGB MP4 camera streams.

```bash
python3 -m lerobot_repair audit --dataset DATASET --output REPORT.json
```

## Recording layout

Use meta/info.json with codebase_version v3.0, integer fps, total_episodes, total_frames and features. Camera keys are the feature names whose dtype is video. Use the standard data/chunk-NNN/file-NNN.parquet, meta/episodes/chunk-NNN/file-NNN.parquet and videos/CAMERA/chunk-NNN/file-NNN.mp4 paths. Chunk and file numbers are nonnegative, padded to at least three digits. All frame shards share one schema. Each source frame row includes index, episode_index, frame_index, timestamp and task_index. Each episode occupies one data shard, starts at local frame 0 and increments frame_index one at a time. Frame timestamps are frame_index / fps, within 0.0001 seconds. Episode metadata has episode_index, length, data/chunk_index, data/file_index, dataset_from_index and dataset_to_index. The interval is half-open in global frame index.

For each camera, episode metadata includes videos/CAMERA/chunk_index, videos/CAMERA/file_index, videos/CAMERA/from_timestamp and videos/CAMERA/to_timestamp. Its half-open interval is on the decoded video's clock. A valid file decodes at timestamp i / fps for frame i, within 0.0001 seconds. A valid interval is on that grid, within the decoded frame count and exactly one frame per episode row. Later episodes may share the file. They must claim disjoint intervals.

## Audit result

Write the following JSON fields. Keep episode IDs numerically sorted and issue codes lexicographically sorted with no repeats.

- schema_version is 1.
- frame_rows and metadata_rows count every corresponding Parquet row, including bad rows that have a usable episode ID.
- dataset_issues contains INDEX_LAYOUT if frame index values in numeric chunk/file and row order differ from 0 through frame_rows minus one. Include TOTALS if info totals differ from the number of distinct frame-table episode IDs or the number of frame rows.
- episodes contains one object with episode_index and issues per ID found in either table. Use NO_FRAME_ROWS, INVALID_FRAME_ROWS, NO_METADATA or DUPLICATE_METADATA as applicable. Frame rows are invalid if the episode spans shards, a local frame number or timestamp fails the sequence rule, or its global indices are not a nonnegative contiguous sequence within that episode. Every episode claiming a duplicated global index is invalid. A different episode may still be usable when there is an index gap elsewhere.
- With one metadata row and valid frame rows, include DATA_RANGE when its length, shard or global interval differs from the frame rows. With one metadata row and valid frame rows, use VIDEO_RANGE/CAMERA for each camera whose claimed file or interval is unreadable, missing or invalid. If two individually valid claims overlap in the same camera and video file, report VIDEO_OVERLAP/CAMERA on both episodes. An invalid data range does not prevent checking that episode's video ranges.

Missing or unparseable required structural input, such as invalid JSON, corrupt Parquet or an episode row with no usable nonnegative integer ID, must exit nonzero and leave an existing report intact. A corrupt MP4 referenced by a valid row is an audit finding. Repeated successful audits of the same input must produce identical bytes.
