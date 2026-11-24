# Five harder robotics software benchmarks

Start with moving-workcell recovery. In the [initial screen](https://www.oddish.app/experiments/9fe9d13b), all five reference and no-op pairs qualified. GPT‑6.2 Sol at xhigh passed workcell scene reconciliation and path certification, then missed the coordinated detour after five fixtures moved. It scored 0.9286 and passed 17 of 18 checks. Fleet recovery, payload commissioning, versioned mapping and incident repair each scored 1.0. The new tasks make decisions under incomplete information and measure their consequences in an independent execution loop.

## 1. Recover a loaded workcell while fixtures move

Build a recovery service for an arm carrying a part to an assembly fixture. It consumes timestamped scene revisions, measured joint positions and velocities, and attachment state. A fixture update can invalidate a plan while the arm is moving. The service must brake within acceleration limits, retain the payload in its collision model, and replan from measured state. A second scene update can arrive before the replacement path is committed.

The deciding case has two moving gates, a long payload, and a refuge between the gates. The robot must brake, enter the refuge, then continue when the second gate opens. A paired case uses the same geometry and reverses the gate schedule. The verifier checks position and velocity continuity, analytic extrema, and swept clearance against declared moving obstacle envelopes. It also checks completion on feasible cases and safe abstention on blocked cases. A reference can join certified braking to a geometric roadmap and search its safe time intervals. Use NIST geometry and authored timing and stop states. [NIST assembly artifacts](https://www.nist.gov/el/intelligent-systems-division-73500/robotic-grasping-and-manipulation-assembly/assembly) · [MoveIt planning-scene updates](https://moveit.picknik.ai/main/doc/examples/planning_scene_ros_api/planning_scene_ros_api_tutorial.html)

## 2. Recover mixed fleets and jointly reschedule two lifts

Build a dispatch and recovery service for fleets that share corridors, holding bays and lifts. One adapter can accept planned paths. The other follows a fixed service loop and accepts pause and resume. Preserve already released route prefixes when jobs arrive, a lift is blocked, or an adapter's latest plan is based on a stale revision.

Crash the coordinator after it sends an entry grant and before the acknowledgement arrives. A stale cancellation arrives while a robot still occupies the first lift. On fresh clearance, a flexible robot can take either lift, and a fixed-loop robot can take only the second. The individually faster route for the flexible robot delays both deliveries. Independently enumerate feasible small joint schedules from the information available at the decision point. Use a simulator to check actual occupancy, released movement authority, single completion of each parcel job, and continued progress on disjoint routes. A passing reference can combine durable grants with joint search on a time-expanded graph. The Open-RMF Hotel demo supplies a multi-floor, two-lift integration. [Open-RMF Hotel and lift demos](https://github.com/open-rmf/rmf_demos#hotel-world) · [VDA 5050 route release semantics](https://github.com/VDA5050/VDA5050/blob/main/VDA5050_EN.md)

## 3. Promote and roll back a navigation map using evidence from new visits

Build a map release service that registers incoming lidar visits, distinguishes occupancy from occlusion, and emits a candidate map that a live Nav2 process can load. Promote that map only after a canary route meets localization and navigation requirements. Older sessions pin their original map bytes. New sessions should see a complete old or new version even when publication is interrupted.

Use Hannover's hall recordings for surveyed position error and coverage across layouts. Add authored raycast scenes with exact occupied, free and unknown cells. In the deciding case, a permanent partition, a parked cart, and an occluded wall are seen in different visits. Feed the candidate's own registration into its evidence update and publication path. Test relocalization on an independent visit and reopened snapshots while promotions race. Compare stable geometry and known changes separately. Inject a failed canary and a restart during publication, then verify rollback by driving a newly launched consumer. Grade surveyed position on the real recordings and changed cell labels in simulation. [Hannover dataset](https://doi.org/10.25835/gkytjesg) · [Nav2 Jazzy Map Server](https://api.nav2.org/nav2-jazzy/html/classnav2__map__server_1_1MapServer.html)

## 4. Recover navigation after localization loses track

Build a localization supervisor that detects divergence, identifies when evidence supports a repair, then safely resumes a route. Start with retrospective ROS 2 bag diagnosis. Move to a closed-loop headless simulator where a decision to stop, reset localization, or replan changes the robot trajectory and future measurements.

Use the TUHH simulated AMCL recordings for held-out diagnosis across layouts with different ambiguity. For the intervention test, fork the same valid route prefix in ROS 2 Jazzy and Gazebo with a planted sensor-time fault, localization restart, or abrupt obstruction. Recompute sensors and motion after each action. A correct intervention needs to reduce localization error, preserve clearance and complete the reachable part of the mission. Include a case where repeating structure makes a confident reset unsafe and a clear case where resetting is necessary to continue. A supervisor that always resets or always stops fails the corresponding control. [TUHH localization-failure dataset](https://doi.org/10.15480/882.18856) · [Jazzy Gazebo control integration](https://control.ros.org/jazzy/doc/gz_ros2_control/doc/index.html)

## 5. Reconcile an actuator controller chain after a partial mode change

Build a ROS 2 control supervisor and hardware adapter for a coupled arm and an independent gripper. The adapter must switch the arm between velocity and position control while maintaining a coherent physical state. It must recover from a lost acknowledgement, a reset on one actuator, or a failed mode write without replaying stale goals or needlessly disabling unrelated controllers.

Use the Jazzy controller-chaining demo to ground the controller interface and a pseudo-terminal bus emulator for the actuator state. In paired cases the same timeout hides a write that was applied or one that never reached the actuator. A delayed pre-transition goal arrives after one joint's position reference resets. The independent verifier owns register values, acknowledgements and the simulated shaft position. It checks controller dependency quiescence, correct physical readback before rearm, stale-goal rejection, measured-position restart and continued operation of the unaffected branch. Withhold a branch in which a device never returns and require an explicit unavailable state. A reference can reconcile each register transition against the vendor control table and activation graph. [ROS 2 controller chaining demo](https://control.ros.org/jazzy/doc/ros2_control_demos/example_12/doc/userdoc.html) · [Dynamixel control table](https://emanual.robotis.com/docs/en/dxl/x/xm430-w350/) · [Jazzy mode-switch report](https://github.com/ros-controls/ros2_control/issues/3620)

## First implementation and workload

The [five-checkpoint workcell revision](../tasks/swe-m2-software-engineering/workcell-replanning/README.md)
implements forecast-aware planning and durable dispatch in the existing planar
workcell. GPT‑6.2 Sol xhigh passed all 16 final missions and scored 1.0 overall.
The missed coordinated detour appears in the earlier third checkpoint, which
scored 0.928571. [Five-checkpoint result](https://www.oddish.app/experiments/8ede1e8f)

For a full spatial benchmark, use moving-workcell recovery first. Supply a pinned ROS 2 Jazzy and MoveIt environment, robot and payload geometry, and one public executable example for each interface. Assign five connected deliveries and use their verifier results for feedback during development.

| Delivery | Engineering work |
| --- | --- |
| Scene and state replay | Reconcile delayed joint and fixture updates in the acquisition clock. Reconstruct payload ownership and plan revisions, and reproduce a scene from recorded inputs. |
| Continuous motion qualification | Check position, velocity, acceleration and loaded swept clearance for the retimed path. Produce clearance evidence that an independent checker can recompute. |
| Timed planning | Find coordinated routes through moving gates and narrow clearances. Choose a safe waiting pose and meet the finish window under all declared tracking envelopes. |
| Execution and recovery | Integrate the planner with the replanning service. Brake from measured position and velocity, invalidate expired scene commitments, and recover safely when a second update arrives during execution. |
| Restart and validation | Recover payload and command ownership after restarting the service. Run whole missions across layouts and interruption schedules, localize regressions, and preserve an audit trail of accepted and rejected commands. |

Design for roughly five engineering days across the five deliveries. The actual workload needs a timed reference and expert run. Fleet recovery has a comparable progression from adapter and custody handling to joint scheduling, revision consistency, fenced takeover and composed replay. Mapping, localization recovery and actuator recovery should likewise include a real service interface and a final independent execution loop.

## Scoring for the below-0.5 target

The model target is GPT‑6.2 Sol at xhigh, using the same Codex configuration as the current screen. For the full workcell task, propose 16 sealed missions in four equally represented families. Each family has three feasible deliveries and one mission that requires a safe stop. Cover changes in gate order, coordinated loaded motion, braking and revision races, and restarts with stale state. Publish the allowed actions, tracking envelopes and operating deadlines. Keep the fixture schedules and combinations private.

The final reward is successful missions divided by 16. A feasible delivery succeeds only if it reaches the goal within the simulated deadline and maintains clearance, motion limits, and current execution authority throughout. A stop mission succeeds only if the arm brakes before the hazard, holds the load and stays stopped until it regains valid authority. A score below 0.5 means the solver completed at most seven mission objectives. An always-stop implementation can qualify for at most four. Keep per-stage flags and per-requirement misses as diagnostics.

Before freezing the case set, certify a feasible trace for each attainable delivery and a safe braking trace for every stop case. The working reference must solve the missions through the same causal interface as the candidate, without access to the witness traces. Verify at least one feasible path for each late disruption given the declared advance notice and latency. Set wall-clock budgets from measured implementation and reference needs, separately from simulated operating deadlines. After freezing the rubric, use repeated independent attempts to measure the target score.

Use the same outcome principle for the other four proposals. A fleet mission preserves physical occupancy and parcel custody while completing feasible deliveries. A map mission activates or correctly rejects a release and supports an independent canary route and pinned readers. A localization mission safely traverses a recoverable incident, or stops on an unrecoverable one. An actuator mission reconciles a physical mode transition, rejects stale commands, and preserves independent control. Require each reference and no-op to qualify before comparing candidate results. Report infrastructure failures and exhausted budgets separately from solved-mission fractions. A single sub-0.5 result is an observed failure under one frozen task version. The proposed tasks' scores remain to be measured.
