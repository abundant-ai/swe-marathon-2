# Publish training-ready data without disturbing the capture

An operator can review the repair plan before approving it. Add a publisher that produces a new LeRobot v3.0 directory from a reviewed plan. Training jobs may still be reading the capture. Keep both earlier commands working and leave the source untouched.

```bash
python3 -m lerobot_repair apply --dataset DATASET --ledger LEDGER.json --plan PLAN.json --output NEW_DATASET
```

Recompute the plan from the current dataset and exact ledger bytes. Require the supplied plan to agree as a JSON value before publishing. Reject stale or altered plans and a plan that keeps no episodes. The output must be outside the source directory, at a path that does not contain either the source or the ledger.

Write kept episodes in increasing original ID order with new dense episode_index and global index values starting at zero. Preserve source action, state, task_index, local frame_index and timestamp values and any other frame columns. Retain the frame table schema. A single native chunk-000/file-000.parquet under data and under meta/episodes is sufficient. Make each episode's native shard references, length and half-open index range agree with the new rows. Copy meta/tasks.parquet unchanged. It maps task names to IDs using a string column called task or __index_level_0__ and an integer task_index. Derive each episode's tasks from its ordered distinct task IDs. An unknown task index must fail publication.

Copy only referenced video files, byte for byte, retaining its chunk and file indices. Set each episode's camera time range to the verified clip bounds divided by fps. Unreferenced frame ranges inside a retained MP4 file may remain. Preserve the feature definitions and update total_frames, total_episodes, total_tasks and the sole train split, which covers all new episode IDs. Recompute dataset-level min, max, mean, population standard deviation and count for action and observation.state. Each of these features is a finite numeric vector of fixed length in the source. Store the statistics in meta/stats.json with vectors for min, max, mean, std and a one-element count array. Preserve other stats only if every row and verified camera interval remains unchanged. Omit unsupported statistics if their data changed.

Add repair-receipt.json in the published root with schema_version 1, source_sha256, ledger_sha256, plan_sha256, output_sha256, episode_map and quarantined. The plan digest is SHA-256 of compact JSON with keys sorted, UTF-8 without ASCII escaping, and no trailing newline. Output fingerprint uses the same file algorithm as the source. The episode_map is a list of [original_id,new_id] pairs in original ID order. quarantined is a list of discarded IDs in ascending order.

Publish the finished directory atomically. Concurrent identical retries may return success and must leave one complete dataset with the same receipt. A later retry to an existing output may succeed only if the receipt and its native file fingerprint match the requested repair. Failed publication must leave any existing destination intact.
