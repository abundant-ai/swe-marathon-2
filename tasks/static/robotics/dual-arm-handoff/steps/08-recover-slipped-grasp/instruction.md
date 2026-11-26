# Resume a transfer after a part slips in the gripper

A clamped part can settle into a different pose without changing hands. The cell interlock holds both arms while the camera surveys the new grasp. Recover the payload transform from the survey, then finish the transfer from the measured cell. A slip can occur either before handoff or after the receiving arm has taken custody. Use the recovered attachment for swept clearance, grasp alignment and delivery. Keep the earlier commands available.

```bash
python3 -m dual_arm dispatch-grasp-recovery --spec PACKET.json --state STATE.json --output REPORT.json
```

## Interlock and survey

Use the Stage 7 packet, receipt, clock and command rules. The packet adds `grasp_epoch`, `survey`, and `observations`. `grasp_epoch` starts at zero. A slip increments it by one at a higher `revision`, with both arms stopped at a measured joint speed of at most 0.025 rad/s. Any outstanding command must have a valid completion receipt before the new epoch is accepted. Only a completed transfer with receiver confirmation can change custody. A window can name the drawn staging cell as in Stage 7, with its `stations` list limiting the authorized handoff poses. The `window` still carries the commissioned grasp poses. The slip invalidates the pose for the physical holder measured at the new epoch.

`survey` stays fixed for a mission. It gives `max_age_ticks` from 1 to 200 ticks, `position_tolerance_m` as a positive distance, and `rotation_tolerance_rad` as a positive angle. An observation carries `epoch`, `owner`, integer `capture_tick`, a `q` map of both six-joint encoder readings, and `world_from_object` in the same pose format as the destination. The camera and encoders are paired at capture. Packets can arrive late, out of order or repeated. Ignore incomplete or invalid observations, records from another epoch or holder, records captured before the new epoch's first measured tick, future captures, and captures older than `max_age_ticks` relative to the current measured tick. Count a capture tick once and keep its first valid observation.

Use the calibrated gripper pose at each observation's encoder reading to estimate `object_from_grasp` for the current holder. Require at least three distinct fresh captures. Find a largest set whose estimates agree pairwise within the survey tolerances, using translation distance in metres and relative rotation angle in radians. Hold when equally supported sets imply incompatible grasps. The fitted pose must agree with its supporting estimates within those tolerances and fit the commissioned grasp bounds. The part is rigid in the holder once the new epoch begins. Carry the recovered transform forward for that arm until a later interlock invalidates it.

## Decisions and receipts

Return the Stage 7 fields plus `grasp`. While waiting for survey evidence, return `surveying` with null `command`, `command_id`, and `grasp`. The interlock owns the hold. If the survey is still unresolved at the deadline, return `blocked`. After solving the current epoch, `grasp` is `{owner,epoch,object_from_grasp,captures}` with the sorted supporting capture ticks. Keep that receipt on subsequent decisions in the same epoch, including after a confirmed transfer. Return null `grasp` in epoch zero and for rejected packets.

After the survey, use the updated grasp to certify motion and replan from the measured pose. The rest of the commissioned geometry, handoff regions, arrival limits and deadline still apply. Persist accepted surveys and command authority before replying. Retain the previous checkpoint's exact retry, rejection and concurrent journal behavior. Separate survey fitting, receipt validation, motion planning and publication.
