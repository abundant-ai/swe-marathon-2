# Contact wrench calibration

A manipulation researcher needs consistent force and motion data after a force–torque sensor is remounted. The tool reconciles wrench coordinates and lever arms, fits the sensor mount and offsets against known loads, and qualifies a compliant pushing model on separate commanded trajectories.

The lab workflow follows recorded tool, object, and force traces in the MIT planar pushing dataset, and a public Pinocchio discussion about expressing contact forces at the correct frame origin. No third-party pushing recordings are redistributed. The contact worlds, load faults and training records are authored. Agent and verifier images contain MuJoCo 3.3.7 and NumPy. The verifier uses native MuJoCo for two-hinge kinematics and independently checks its point Jacobian by finite differences. The disc contact and table drag model is an explicit reduced-order approximation. [MIT Push dataset](https://mcube.mit.edu/push-dataset/) · [Contact Jacobian discussion](https://github.com/stack-of-tasks/pinocchio/discussions/2201) · [MuJoCo API](https://mujoco.readthedocs.io/en/3.3.7/APIreference/APIfunctions.html)

| Dimension | Evidence and limitations |
| --- | --- |
| Novelty | This benchmark couples wrench frames and sensor calibration to held-out contact dynamics. The existing payload-commissioning task identifies terminal load inertias and diagnoses residuals, while Workcell Replanning checks collision and path feasibility. Comparisons outside these assets are unverified. |
| Verifiability | Graders independently generate lab-frame loads, use native kinematics and finite differences, and simulate forces and trajectories from planted material coefficients. They check both compliance and anisotropic drag. |
| Realism | Force transforms change when coordinate axes and moment reference points differ. Labels require an independently instrumented load fixture. The planar simulator omits object spin, friction hysteresis, hardware compliance outside the prescribed model, and real sensor drift. |
| Difficulty | Full recovery combines noncommuting frame effects, robust identification under contamination, rank checks, unilateral contact, and integration without access to held-out states. Held-out model difficulty is unmeasured. |
| Feasibility | Rigid kinematics, robust small linear models, and direct integration are sufficient for the declared CPU scope. |

## Verification

The verifier scores the fraction of named checks reached through the CLI, cumulatively through three checkpoints. Geometry checks require fully correct outputs for a specified arm and a second independent frame geometry. Calibration checks cover two hidden mounts and deficient excitation. Qualification checks require identifiable parameters and held-out force and motion across two plants. Error-case checks qualify only with working functional evidence. The practical shortcut risks are raw-data frame reuse, ordinary nonrobust fitting, and direct playback of held-out ground truth. The fixtures supply different frame layouts, seeded force faults, and no held-out observations beyond initial state and controls. Lab-hardware validity and hosted process isolation remain unverified.

## Development log

### 2026-11-24

Implemented the three command contracts, reference, native geometry checks and independently generated contact predictions. The packaged local reference scored 1.0 and the no-op scored 0.0 at each checkpoint. The final report passed all 11 named checks. The maintained pytest suite passed and Oddish preflight reported no findings. Hosted execution remains unverified.
