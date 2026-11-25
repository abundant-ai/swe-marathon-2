# BARN constrained navigation qualification

Plan and execute short differential-drive traversals through cluttered occupancy layouts. Record when the physical robot completes, collides, or runs out of time. Handle revised map occupancy in motion and classify a separate ground-truth traversal.

## Design dimensions

| Dimension | Evidence and remaining questions |
| --- | --- |
| Novelty | The BARN Challenge evaluates continuous collision-free traversal on unfamiliar worlds and benefits from shorter runs. This task adds a software deliverable that combines portable map planning, revision-aware navigation, and independent trace classification. The repository's Nav2 docking task ends at a charger and uses taught staging edges. Here there are no taught routes and goals are general map cells. Comparisons to other SWE benchmark suites remain unverified. [BARN Challenge](https://www.cs.utexas.edu/~xiao/Research/BARN_Challenge/BARN_Challenge.html) |
| Verifiability | Independent checks compare shortest lattice paths, actuate actual submitted twist commands, measure swept footprint clearance and elapsed simulation ticks, and classify separately recorded traces using analytic fixtures. |
| Realism | The main public map is a conservative occupancy crop of an authentic BARN challenge world. Authored unknown layouts add staggered one-cell gaps, a physical footprint pinch, and timed closures. A 2D differential-drive plant integrates exact constant-twist commands. Native Jackal mechanics, Gazebo, ROS and Nav2 are outside this pilot. [BARN maps and source workflow](https://www.cs.utexas.edu/~xiao/BARN/BARN.html) |
| Difficulty | Center-only planning admits infeasible pinches. A committed route may become unavailable during a sensor dropout. The controller must replan from a continuous observed pose and use the most recent map revision without leaking future updates. This is a compact pilot with no measured five-day workload or model difficulty. |
| Initial feasibility | An inflated-collision lattice, exact segment-to-cell separation, shortest successor trees and bounded pure-turn/forward tracking solve the authored courses. A different safe command strategy remains valid. Hosted control execution is pending. |

The raster uses 53 numbered cylinder centers, IDs 126–178, retained from World 0. It conservatively replaces each cylinder footprint with an occupied square of 0.15 m edge length, translates a crop, and uses task-specific world bounds, footprint and endpoints. Other layouts are authored. The runtime retains the source attribution and MIT notice in `environment/example/NOTICE.txt`. [World 0 source](https://github.com/Daffan/the-barn-challenge/blob/main/jackal_helper/worlds/BARN/world_0.world) · [MIT license](https://github.com/Daffan/the-barn-challenge/blob/main/LICENSE)

## Verification

1. Verify shortest cardinal routes on the source-derived crop and authored map, and safely reject an infeasible footprint pinch.
2. Run actual differential-drive controls on two reachable courses and one sealed negative control. Score physical completion, collision-free swept motion, and compliance with a travel deadline.
3. Admit or reject live map updates, pause for localization loss, resume when a gate opens, and independently classify measured collision, completion and timeout.

The reward at each checkpoint is the fraction of its cumulative missions that pass. The final reward is their mean. Mission reports contain observed path distance, minimum clearance and completion tick. Scoring the actual trajectory prevents a fake completed status from earning a live mission.

## Hackability assessment

The highest assessed risk is medium for fitting a small fixture set. The verifier rotates initial headings, varies clearance and uses both real-source occupancy and privately authored independent layouts. It applies candidate velocities before computing outcomes. The separate verifier stages regular artifacts only, uses a lower-privilege candidate process and keeps reward output root-only. This has been inspected locally. Hosted isolation and a broader held-out challenge-world set remain unassessed.

## Development log

### 2026-11-24

Implemented the three-stage qualification task and extracted the attributed World 0 obstacle crop. Generate the task with `python3 -B scripts/package_task.py`. The local executable controls and Oddish preflight establish package behavior. Hosted model runs and formal task-quality ratings remain pending.
