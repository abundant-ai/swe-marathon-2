# Oddish QA reconciliation

This ledger covers the reviewed versions in the [original experiment](https://www.oddish.app/experiments/6dc2a858). Each finding retains its original priority. New executions and measurements apply to the revision described in the task README.

## Fixed separate-worker file layout

The verifier restores the condition’s declared public observations into /app/work before rebuilding. Both absolute and relative paths resolve to the same read-only inputs. The worker can write reconstruction scratch files in the working directory.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | must fix | [Observation files are missing from /app/work in the separate verifier container](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| swapped, v1 | must fix | [Documented /app/work observation path is missing in the separate verifier](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |
| none, v1 | must fix | [Verifier omits supplied public files from /app/work and runs in a read-only temp directory](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |

## Disclosed source transfer and bounds

The brief states the single submitted Python module, the 2 MiB source limit, and how to embed derived data or rebuild it from supplied observations. The public rehearsal starts from that same deployment layout.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | must fix | [Undisclosed single-file collection drops companion data and helper files in /app/work](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| matched, v1 | must fix | [Undisclosed 2 MiB file-size limit on submission.py rejects valid inline meshes](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| swapped, v1 | must fix | [Undisclosed single-file collection drops auxiliary modules and pre-fitted data files](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |
| swapped, v1 | must fix | [Undisclosed 2 MiB size limit on submission.py rejects valid pre-fitted meshes](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |
| none, v1 | must fix | [Undisclosed 2 MiB file-size limit on submission.py rejects valid pre-fitted meshes](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |
| none, v1 | must fix | [Single-file artifact collection silently drops auxiliary pre-fitted files and helper modules](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |

## Fixed writeability and tool parity

Both images include FFmpeg and the numerical dependencies used by the reference. The verifier makes the workspace sticky and writable while protecting individual inputs. Local extraction and clean temporary files are part of the public rehearsal.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | should fix | [Working directory is read-only in verifier worker unlike writable /app/work in solver container](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| matched, v1 | should fix | [ffmpeg is installed in the solver container but missing from the verifier container](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| swapped, v1 | must fix | [Undisclosed read-only working directory in verifier worker breaks local temp writes](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |

## Replaced the opaque oracle

The reference now emits executable room primitives, RGB feature matching, plane and contour fits, native rendering, mesh subdivision and a multiview color solve. It reads the supplied photographs, video frames and camera track. No precomputed reconstruction archive enters the new runtime. The author’s manually traced public features remain explicit inputs to the reference program.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | must fix | [Reference solution embeds opaque precomputed reference.npz instead of readable reconstruction source](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| swapped, v1 | must fix | [Reference solution embeds opaque precomputed reference.npz instead of reconstructing from inputs](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |
| none, v1 | must fix | [Reference solution embeds opaque precomputed /solution/reference.npz instead of computing reconstruction](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |

## Fixed candidate artifact error handling

The maintained reader checks artifact type and size before parsing, converts unusable transferred paths into candidate-domain failures and classifies malformed numerical archives. Trusted missing fixtures still raise infrastructure errors. The earlier clean-source replay and harness distinguish these outcomes.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | should fix | [Uncaught OSError and archive errors on artifact conflicts leave attempts unscored](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a) |
| swapped, v1 | should fix | [Uncaught OSError in read_regular() on symlink conflicts crashes verify.py unscored](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9) |

## Accepted observed evaluation awareness

At step 7 the agent predicted that held-out renders and exposed part labels would be checked. Those are natural checks on the requested deliverable. The report marks causal influence false. The prediction establishes awareness and supplies no evidence of access to withheld masks or depth.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| matched, v1 | must fix | [The solver recognized its current session as an evaluation.](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a?trial=swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a-12) |

## Confirmed missing target evidence in diagnostic controls

The swapped images come from A and correspond to the supplied A track, while the requested output remains B. Both A and B tracks remain available in all three conditions. The blind condition removes optical observations. Only the matched condition is independently solvable from scene evidence. Exclude the two diagnostic conditions from standalone task difficulty and qualification scores.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| swapped, v1 | must fix | [The starting files provide capture A, but the task requires workspace B.](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9?trial=swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9-2) |
| swapped, v1 | must fix | [The solver image copies RGB frames that do not match the B pose track.](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9?trial=swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9-3) |
| none, v1 | must fix | [Missing visual observation inputs (observation.png, clip.mp4, frames.zip) make workspace B reconstruction unsolvable](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |

## Removed unnecessary solver feedback

The public command prints mesh dimensions and counts. Its receipt binds the source and array contents so the verifier can independently reproduce them. The digest cannot establish an historical tool invocation or reveal a hidden scoring threshold.

| Reviewed variant | Priority | Oddish finding |
|---|---|---|
| none, v1 | must fix | [Solver-facing smoke.py, test_receipt.json, and instruction.md reveal internal source-digest tracking](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0) |

## Experiment dashboard cross-check

The experiment dashboard groups 26 records into the categories below. It includes trial narratives and merged findings, so its count differs from the task-level export. Both views refer to the same underlying runs.

| Dashboard category | Records | Evidence and disposition |
|---|---:|---|
| Other | 19 | Task audit findings are itemized above.  |
| Required files are missing | 3 | The named trials are visual interventions. The target mismatch or unobservable input is real and is the experimental manipulation. The matched task ships the required evidence. The intervention reference builds a valid fallback. [Trial 2](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0?trial=swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0-2) [Trial 3](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0?trial=swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0-3) [Trial 4](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0?trial=swe-m2_ai-research_telephone-contact-reconstruction-none-75282dc0-4) |
| Task environment is broken | 2 | The named trials are visual interventions. The target mismatch or unobservable input is real and is the experimental manipulation. The matched task ships the required evidence. The intervention reference builds a valid fallback. [Trial 2](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9?trial=swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9-2) [Trial 3](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9?trial=swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9-3) |
| Agent can access restricted information | 1 | The cited trajectory statements establish evaluation awareness. No cited statement identifies a private file or its contents. [Trial 12](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a?trial=swe-m2_ai-research_telephone-contact-reconstruction-correct-10b5125a-12) |
| Task depends on an outside source | 1 | The packaged optical file is deliberately substituted in this diagnostic. Rebuilding requires no external service. [Trial 2](https://www.oddish.app/tasks/swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9?trial=swe-m2_ai-research_telephone-contact-reconstruction-swapped-908d14d9-2) |

## Rebuilding the image controls

The nine-package release used registered alternate observations. The matched telephone release can be restored with `python3 scripts/prepare_data.py --qualified-runtime dist/telephone-qualified`. Each 3D intervention changes the optical files in both the candidate and deployment workspaces. Candidate-visible source, pose files and instructions are identical across the three conditions. The hosted experiments list the exact task revisions and trial IDs. [Baseline experiment](https://www.oddish.app/experiments/9a9cd757) · [Harbor implementation reviews](https://www.oddish.app/experiments/50baaa6f)

## Held-out measurement limits

For a predicted footprint P and a traced footprint T, the numerator counts predicted pixels inside the one-pixel-eroded T. The denominator adds all pixels in that eroded interior to predicted pixels outside the one-pixel-dilated T. Predictions confined to the uncertainty band do not inflate the numerator. Fractional sRGB channels are rounded to bytes before interpolation, as documented in the revised brief. The rehearsal remains diagnostic.

All four inner-wall masks share a boundary with the aperture of the top annulus. In the four photographs the colored print on the inner cardboard is visible across the aperture. This supports the projected label; a binary mask alone cannot establish a hollow volume. The independent depth diagnostic has 106 inner-wall rays and only eight handle rays. Contact depth, handset separation and cord exclusion should not be reported as independently established by the scalar reward. [Measured contact support](checks/contact-depth-diagnostic.json)
