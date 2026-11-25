"""Drive a candidate coating supervisor through a trusted interrupted physical mission."""

from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, replace
import math
from pathlib import Path
from typing import Any, Literal, Protocol

from applied_history import AppliedHistory, Motion, parse_receipt
from coating_scene import CoatingScene, Pose, rigid_pose
from live_controller import LiveController, ObservedMotion, PressureSag, PressureSample, brake_knots
from native_arm import NativeArm
from offline_plan import arm_lever_bound, joint_violations, rotating_radius
from process_trace import ProcessTrace, TraceEvidence
from scene_clearance import SceneClearance
from swept_clearance import certify_clearance
from trajectory import Knot, Vector, parse_knots, segments


Document = dict[str, Any]


class Runner(Protocol):
    """Send one NDJSON request with optional candidate process restart."""

    def __call__(self, request: Document, *, restart: bool = False) -> Document | None: ...


@dataclass(frozen=True)
class LiveScenario:
    """Independent fault schedule and ground truth for one live qualification case."""

    interrupt_after_ml: float
    remount_registration: Mapping[str, Any] | None = None
    world_collision: list[Document] | None = None
    expect_blocked: bool = False
    flow_gain: float = 1.0
    stale_running: bool = False
    registration_review_periods: int = 0
    world_update_during_motion: bool = False
    prime_delay_periods: int = 0
    pressure_sag: PressureSag | None = None


@dataclass(frozen=True)
class InterruptionEvidence:
    """Controller conditions at one physical fault boundary."""

    motion_id: str
    time_ns: int
    readback_age_ns: int
    spray_permitted: bool
    scene_revision: int | None
    emitted_ml: float


@dataclass(frozen=True)
class LiveEvidence:
    """Measured mission outcome. Unresolved indicates missing verifier proof."""

    status: Literal["passed", "failed", "unresolved"]
    explanations: tuple[str, ...]
    process: TraceEvidence
    elapsed_ns: int
    issued_motions: int
    stop_commands: int
    first_flow_interruption_ns: int | None
    interruption_readback_age_ns: int | None
    interruption_spray_permitted: bool | None
    interruption_scene_revision: int | None
    interruptions: tuple[InterruptionEvidence, ...]
    minimum_sampled_clearance_m: float | None
    clearance_samples: int
    updates_after_remount: int
    delayed_receipt_hold_observed: bool
    stale_evidence_hold_observed: bool
    registration_review_hold_packets: int
    restarted_and_retried: bool
    cold_progress_checked: bool
    physical_emitted_ml: float
    commanded_ml_during_motion: float
    priming_suppressed_ml: float
    pressure_suppressed_ml: float
    pressure_samples: tuple[PressureSample, ...]


class _SubmissionError(Exception):
    """Candidate output violates the live contract or measured mission."""


class _UnresolvedError(Exception):
    """The evaluator cannot establish a required independent condition."""


@dataclass(frozen=True)
class _Epoch:
    """Immutable scene and part registration used for one issued motion."""

    revision: int
    scene: CoatingScene
    home: Pose
    registered: bool
    rotating_radius_m: float


def _close_vectors(a: Vector, b: Vector) -> bool:
    """Compare public JSON configurations with only roundoff tolerance."""
    return all(math.isclose(x, y, abs_tol=1e-9, rel_tol=0.0) for x, y in zip(a, b, strict=True))


class _Mission:
    """Own all physical state and delivery, with a separate submitted process."""

    def __init__(
        self, job: Mapping[str, Any], registration: Mapping[str, Any], runner: Runner,
        urdf: Path, srdf: Path, scenario: LiveScenario, max_process_step_ns: int, max_cell_edge_m: float,
        *, followups: tuple[LiveScenario, ...] = (),
    ) -> None:
        self.schedule = (scenario, *followups)
        previous = 0.0
        for phase in self.schedule:
            if not math.isfinite(phase.interrupt_after_ml) or phase.interrupt_after_ml <= previous:
                raise ValueError("Live interruptions require increasing positive measured flow thresholds")
            if phase.flow_gain != scenario.flow_gain:
                raise ValueError("Follow-up interruptions must use the mission's pump calibration")
            if phase.registration_review_periods < 0 or (phase.registration_review_periods and (
                phase.expect_blocked or (phase.remount_registration or {}).get("status") != "registered"
            )):
                raise ValueError("A registration review requires a confirmed remount and a recovery mission")
            if phase.world_update_during_motion and (
                phase.world_collision is None or phase.remount_registration is not None or phase.stale_running
            ):
                raise ValueError("A moving world update requires world geometry and its own interruption")
            previous = phase.interrupt_after_ml
        if any(phase.expect_blocked for phase in self.schedule[:-1]):
            raise ValueError("Only the last interruption can hold through the deadline")
        if any(phase.prime_delay_periods or phase.pressure_sag is not None for phase in followups):
            raise ValueError("Pump transients are configured once for the whole mission")
        self.job, self.runner, self.scenario = job, runner, scenario
        self.motion = job["motion"]
        self.deadline = self.motion["max_duration_ns"]
        self.max_step_ns = max_process_step_ns
        self.plant = LiveController(job, flow_gain=scenario.flow_gain, prime_delay_periods=scenario.prime_delay_periods,
                                    pressure_sag=scenario.pressure_sag)
        model = job["robot_model"]
        self.arm = NativeArm(urdf, srdf, model["arm_joints"], model["tool_frame"])
        self.geometry = SceneClearance(self.arm)
        self.arm_radii = (arm_lever_bound(self.arm),) * 6
        scene = CoatingScene.from_job(job)
        home = rigid_pose(registration["base_from_part_home"])
        self.epoch = _Epoch(job["scene_revision"], scene, home, registration["status"] == "registered",
                            rotating_radius(scene, home))
        self.world_records = list(job.get("world_collision", []))
        self.moving_world = self._next_scene() if scenario.world_update_during_motion else None
        self.world_interruptions: dict[str, tuple[int, _Epoch]] = {}
        self.process = ProcessTrace(scene, job["target_faces"], job["recipe"], max_cell_edge_m=max_cell_edge_m)
        self.sequence = 0
        self.applied = AppliedHistory()
        self.authority: dict[str, Motion] = {}
        self.issued_epochs: dict[str, _Epoch] = {}
        self.commands: dict[str, Document] = {}
        self.latest: tuple[Document, Document] | None = None
        self.integrated: set[str] = set()
        self.stops = 0
        self.interrupted_at: int | None = None
        self.interruptions: list[InterruptionEvidence] = []
        self.previous_stop_receipt: Document | None = None
        self.clearance_count = 0
        self.minimum_clearance = None
        self.remount_motions = 0
        self.remount_revision: int | None = None
        self.held_for_receipt = False
        self.held_for_freshness = False
        self.registration_review_hold_packets = 0
        self.restarted = False
        self.cold_progress = False

    def _clearance(self, knots: tuple[Knot, ...], epoch: _Epoch, *, observed: bool = True) -> None:
        """Check joint bounds and continuous separation for an entire Hermite sequence."""
        pieces = tuple(segments(knots))
        issues = joint_violations(self.motion, self.arm, pieces)
        if issues:
            raise _SubmissionError(issues[0])

        def distance(q_rad: Vector) -> float:
            self.arm.set_q(q_rad[:6])
            return self.geometry.at(epoch.scene.place(q_rad[6], epoch.home))

        for piece in pieces:
            result = certify_clearance(piece, distance, self.motion["min_clearance_m"],
                                       self.arm_radii, epoch.rotating_radius_m)
            if observed:
                self.clearance_count += result.samples
                self.minimum_clearance = (result.minimum_sample_m if self.minimum_clearance is None
                                          else min(self.minimum_clearance, result.minimum_sample_m))
            if result.status == "violation":
                raise _SubmissionError("Observed continuous clearance violation.")
            if result.status == "unresolved":
                raise _UnresolvedError("Continuous clearance could not be certified.")

    def _integrate(self, measured: ObservedMotion) -> None:
        """Integrate each physical motion once, independent of transport delivery."""
        identity = measured.command_id
        if identity in self.integrated:
            return
        epoch = self.issued_epochs[identity]
        samples = tuple(measured.samples)
        spans = ((samples, epoch),)
        revision = self.world_interruptions.get(identity)
        if revision is not None:
            event_ns, new_epoch = revision
            boundary = (event_ns - measured.issued_ns) // self.plant.period_ns
            assert 0 < boundary < len(samples) - 1 and samples[boundary].t_ns == event_ns
            spans = ((samples[:boundary + 1], epoch), (samples[boundary:], new_epoch))
        for knots, physical_epoch in spans:
            self._clearance(knots, physical_epoch)
            self.process.scene = physical_epoch.scene
            self.process.append(self.arm, knots, physical_epoch.home, max_step_ns=self.max_step_ns)
        self.integrated.add(identity)

    def _settled(self) -> bool:
        """Determine whether all stopped physical prefixes have been delivered."""
        return all(self.applied.complete(self.authority[entry.command_id], entry.samples[-1].t_ns) is not None
                   for entry in self.plant.finished)

    def _fresh_rest(self, request: Document) -> bool:
        """Check the public motion-authority conditions from the packet sent."""
        reading = request["controller"]
        age = self.plant.now_ns - reading["measured_ns"]
        return (0 <= age <= self.motion["state_max_age_ns"] and reading["mode"] in ("idle", "stopped")
                and all(abs(v) <= self.motion["stop_velocity_rad_s"] for v in reading["qd_rad_s"]))

    def _execute(self, command: Document, request: Document) -> None:
        """Verify a proposed trajectory before allowing it to drive the plant."""
        if not (self._fresh_rest(request) and self._settled() and self.plant.permitted and self.epoch.registered):
            raise _SubmissionError("Issued motion before fresh stopped authority and complete measured history.")
        if type(command.get("scene_revision")) is not int or command["scene_revision"] != self.epoch.revision:
            raise _SubmissionError("Issued motion for the wrong scene revision.")
        try:
            knots = parse_knots(command.get("trajectory"), self.plant.period_ns, self.job["recipe"]["max_flow_ml_s"])
        except ValueError as error:
            raise _SubmissionError(str(error)) from error
        start, end = knots[0], knots[-1]
        if (start.t_ns != 0 or not _close_vectors(start.q_rad, self.plant.q)
                or not _close_vectors(start.qd_rad_s, self.plant.qd)):
            raise _SubmissionError("New trajectory does not start at the measured halted position and velocity.")
        if end.t_ns + self.plant.now_ns > self.deadline:
            raise _SubmissionError("The issued trajectory finishes after the mission deadline.")
        if any(abs(value) > self.motion["stop_velocity_rad_s"] for value in end.qd_rad_s):
            raise _SubmissionError("Issued trajectory ends without a stopped configuration.")
        self._clearance(knots, self.epoch, observed=False)
        identity = command["command_id"]
        self.authority[identity] = Motion(identity, self.epoch.revision, self.plant.now_ns)
        self.issued_epochs[identity] = self.epoch
        if self.remount_revision is not None and self.epoch.revision >= self.remount_revision:
            self.remount_motions += 1
        self.plant.accept(identity, self.epoch.revision, knots)

    def _stop(self, command: Document) -> None:
        """Bind a stop to the current motion and certify its configured brakes."""
        active = self.plant.current
        if active is None or self.plant.mode != "running" or command.get("motion_id") != active.command_id:
            raise _SubmissionError("Stop does not identify the current moving command.")
        profile = brake_knots(self.plant.now_ns, self.plant.q, self.plant.qd, self.motion)
        self._clearance(profile, self.epoch, observed=False)
        self.plant.stop(profile)
        self.stops += 1

    def _complete(self, request: Document) -> bool:
        """Determine if terminal completion matches independent physical evidence."""
        process = self.process.evidence()
        return (self._fresh_rest(request) and self._settled() and process.enabled_samples > 0
                and not process.off_recipe_samples and process.dose.qualified
                and math.isclose(self.plant.q[6], self.job["final_positioner_rad"], rel_tol=0.0, abs_tol=1e-8))

    def _expected_blocked(self, request: Document) -> bool:
        """Prove no time remains after measured history was reconciled."""
        return (self.scenario.expect_blocked and self.plant.now_ns >= self.deadline
                and self._fresh_rest(request) and self._settled() and not self._complete(request))

    def _command(self, reply: Document, request: Document) -> None:
        """Validate one new execution/stop or deduplicate its exact already issued form."""
        command = reply.get("command")
        if command is None:
            return
        if not isinstance(command, dict) or reply["status"] in ("complete", "blocked"):
            raise _SubmissionError("Invalid command in a terminal or malformed reply.")
        identity = command.get("command_id")
        if not isinstance(identity, str) or not identity:
            raise _SubmissionError("Command has no stable ID.")
        previous = self.commands.get(identity)
        if previous is not None:
            if previous != command:
                raise _SubmissionError("Command ID was reused for a different instruction.")
            return
        if command.get("kind") == "execute" and reply["status"] == "ready":
            self._execute(command, request)
        elif command.get("kind") == "stop" and reply["status"] == "waiting":
            self._stop(command)
        else:
            raise _SubmissionError("Command kind conflicts with the reported supervisor status.")
        self.commands[identity] = deepcopy(command)

    def _call(
        self, *, receipts: tuple[Document, ...] = (), scene: Document | None = None,
        measured_ns: int | None = None, controller: Document | None = None, restart: bool = False,
    ) -> str:
        """Send one accepted observation, checking the submitted action on the plant."""
        for record in self.plant.finished:
            self._integrate(record)
        records = [parse_receipt(item, self.authority, self.plant.period_ns, self.job["recipe"]["max_flow_ml_s"])
                   for item in receipts]
        self.applied = self.applied.extend(records)
        reading = self.plant.observation(measured_ns=measured_ns) if controller is None else controller
        request = {"seq": self.sequence, "now_ns": self.plant.now_ns, "spray_permitted": self.plant.permitted,
                   "controller": reading,
                   "scene": scene, "receipts": list(receipts)}
        reply = self.runner(deepcopy(request), restart=restart)
        if reply is None:
            raise _SubmissionError(f"No reply to controller packet {self.sequence}.")
        if (not isinstance(reply, dict) or type(reply.get("seq")) is not int or reply["seq"] != self.sequence
                or "command" not in reply):
            raise _SubmissionError(f"Invalid reply to controller packet {self.sequence}.")
        status = reply.get("status")
        if status == "rejected":
            raise _SubmissionError(f"Rejected valid controller packet {self.sequence}.")
        if status not in ("waiting", "ready", "blocked", "complete"):
            raise _SubmissionError(f"Invalid reply status for controller packet {self.sequence}.")
        self._command(reply, request)
        if status == "complete" and not self._complete(request):
            raise _SubmissionError("Reported complete without a qualified measured result at rest.")
        if status == "blocked" and not self._expected_blocked(request):
            raise _SubmissionError("Reported blocked before proven infeasibility in this case.")
        if (status in ("complete", "blocked") and self.interrupted_at is None):
            raise _UnresolvedError("The physical mission ended before its intended interruption.")
        self.latest = deepcopy(request), deepcopy(reply)
        self.sequence += 1
        if restart:
            self.cold_progress = True
        return status

    def _retry(self) -> None:
        """Cold-restart and require exactly the latest committed reply."""
        assert self.latest is not None
        request, expected = self.latest
        if self.runner(deepcopy(request), restart=True) != expected:
            raise _SubmissionError("Cold retry changed the committed response or command ID.")
        self.restarted = True

    def _invalid(self, request: Document, wanted_sequence: int | None) -> None:
        """Require a rejection without applying any of the packet's contents."""
        result = self.runner(deepcopy(request), restart=False)
        if result != {"seq": wanted_sequence, "status": "rejected", "command": None}:
            raise _SubmissionError("Malformed or conflicting packet did not receive a transactional rejection.")

    def _transaction_probes(self, accepted_receipt: Document) -> None:
        """Test conflicting receipt IDs, altered retries, and skipped sequences."""
        assert self.latest is not None
        original, _ = self.latest
        conflict = deepcopy(accepted_receipt)
        sample = conflict["samples"][0]
        sample["flow_ml_s"] = (0.0 if sample["flow_ml_s"] else self.job["recipe"]["max_flow_ml_s"] / 2)
        next_request = deepcopy(original)
        next_request.update(seq=self.sequence, scene=None, receipts=[conflict])
        self._invalid(next_request, self.sequence)
        altered = deepcopy(original)
        altered["spray_permitted"] = not altered["spray_permitted"]
        self._invalid(altered, original["seq"])
        self._invalid(dict(original, seq=self.sequence + 1, scene=None, receipts=[]), self.sequence + 1)
        self._invalid(dict(original, seq="invalid", scene=None, receipts=[]), None)
        self._retry()

    def _next_scene(self, *, under_review: bool = False) -> tuple[_Epoch, Document] | None:
        """Prepare a physical scene and the report for its next revision."""
        replacement = self.scenario.remount_registration
        new_world = self.scenario.world_collision
        if replacement is None and new_world is None:
            return None
        world_records = self.world_records if new_world is None else new_world
        scene = replace(self.epoch.scene,
                        world=CoatingScene.from_job({**self.job, "world_collision": world_records}).world)
        home = self.epoch.home if replacement is None else rigid_pose(replacement["base_from_part_home"])
        registered = self.epoch.registered if replacement is None else replacement["status"] == "registered"
        if under_review:
            assert replacement is not None
            registered = False
            review_epoch = f"{replacement['capture_epoch']}-review"
            replacement = {"job_id": self.job["job_id"], "capture_epoch": review_epoch,
                           "status": "review", "base_from_part_home": None, "capture_ids": []}
        epoch = _Epoch(self.epoch.revision + 1, scene, home, registered, rotating_radius(scene, home))
        report = {"scene_revision": epoch.revision, "world_collision": world_records, "registration": replacement}
        return epoch, report

    def _scene_update(self, *, under_review: bool = False) -> Document | None:
        """Apply a fixture or world revision while the controller is at rest."""
        update = self._next_scene(under_review=under_review)
        if update is None:
            return None
        epoch, report = update
        self.arm.set_q(self.plant.q[:6])
        if self.geometry.at(epoch.scene.place(self.plant.q[6], epoch.home)) < self.motion["min_clearance_m"]:
            raise _UnresolvedError("Authored scene update violates clearance at the stopped pose.")
        self.epoch = epoch
        self.world_records = report["world_collision"]
        if report["registration"] is not None and epoch.registered:
            self.remount_revision = epoch.revision
        return report

    def _ready_to_interrupt(self, plant: LiveController) -> bool:
        """Choose a measured-flow boundary with a certifiable configured stop envelope."""
        record = plant.current
        if (plant.mode != "running" or record is None or len(record.samples) < 4
                or record.samples[-1].flow_ml_s <= 0 or plant.emitted_ml < self.scenario.interrupt_after_ml):
            return False
        if not any(sample.flow_ml_s > 0 for sample in record.samples[:-1]):
            return False
        profile = brake_knots(plant.now_ns, plant.q, plant.qd, self.motion)
        if profile[-1].t_ns >= self.deadline:
            return False
        try:
            self._clearance(profile, self.issued_epochs[record.command_id], observed=False)
            if self.moving_world is not None:
                self._clearance(profile, self.moving_world[0], observed=False)
        except (_SubmissionError, _UnresolvedError):
            return False
        return True

    def _normal_receipts(self) -> tuple[Document, ...]:
        """Deliver finished motions whose chronological trace has not been sent."""
        return tuple(receipt for entry in self.plant.finished if entry.command_id not in self.integrated
                     for receipt in entry.receipts())

    def _await_fault(self, *, restart: bool = False) -> None:
        """Follow an actual planned run until physical dose permits the injected fault."""
        plant = self.plant
        while plant.now_ns < self.deadline:
            first_motion = not self.authority
            self._call(receipts=self._normal_receipts(), restart=restart)
            restart = False
            if first_motion and self.authority:
                self._retry()
            plant.advance()
            if not self._ready_to_interrupt(plant):
                continue
            if self.scenario.stale_running:
                assert self.latest is not None
                cached = self.latest[0]["controller"]
                assert plant.current is not None
                if cached["mode"] != "running" or cached["command_id"] != plant.current.command_id:
                    continue
                expires = cached["measured_ns"] + self.motion["state_max_age_ns"]
                periods = max(0, (expires - plant.now_ns) // plant.period_ns + 1)
                if periods:
                    projected = deepcopy(plant)
                    projected.advance(periods)
                    if not self._ready_to_interrupt(projected):
                        continue
                    plant.advance(periods)
            self.interrupted_at = plant.now_ns
            return
        if plant.emitted_ml < self.scenario.interrupt_after_ml:
            raise _SubmissionError("No qualifying physical coating reached the fault threshold.")
        raise _UnresolvedError("No certifiably clear braking opportunity occurred after measured coating.")

    def _interrupt(self) -> None:
        """Inject the configured running fault and verify stop and reconciliation."""
        plant = self.plant
        active = plant.current
        assert active is not None and self.interrupted_at == plant.now_ns
        scene = None
        controller = None
        if self.moving_world is not None:
            self.epoch, scene = self.moving_world
            self.world_records = scene["world_collision"]
            self.world_interruptions[active.command_id] = plant.now_ns, self.epoch
            failure = "An active world revision did not stop the running motion."
        elif self.scenario.stale_running:
            assert self.latest is not None
            controller = self.latest[0]["controller"]
            failure = "A stale controller readback did not stop the running motion."
        else:
            plant.set_permit(False)
            failure = "A live permission revocation did not issue a stop for the running motion."
        readback_age = 0 if controller is None else plant.now_ns - controller["measured_ns"]
        self.interruptions.append(InterruptionEvidence(
            active.command_id, plant.now_ns, readback_age, plant.permitted,
            None if scene is None else scene["scene_revision"], plant.emitted_ml,
        ))
        self._call(controller=controller, scene=scene)
        if plant.mode != "stopping":
            raise _SubmissionError(failure)
        while plant.mode == "stopping":
            plant.advance()
            if plant.mode == "stopping":
                self._call()
        stopped = plant.current
        assert stopped is not None
        first, missing, last = stopped.receipts(3)
        scene = None if self.moving_world is not None else self._scene_update(
            under_review=bool(self.scenario.registration_review_periods)
        )
        receipts = (last, first, last)
        if self.previous_stop_receipt is not None:
            receipts = (*receipts, self.previous_stop_receipt)
        self._call(receipts=receipts, scene=scene)
        self._transaction_probes(last)
        plant.advance()
        if not self.scenario.expect_blocked:
            plant.set_permit(True)
        self._call()
        if plant.mode != "stopped":
            raise _SubmissionError("Motion was granted with a gap in the stopped receipt history.")
        self.held_for_receipt = True
        stale_age = self.motion["state_max_age_ns"]
        stopped_ns = stopped.samples[-1].t_ns
        if plant.now_ns - stopped_ns <= stale_age:
            plant.advance((stale_age - (plant.now_ns - stopped_ns)) // plant.period_ns + 1)
        self._call(receipts=(missing,), measured_ns=stopped_ns)
        if plant.mode != "stopped":
            raise _SubmissionError("Motion was granted from a stale stop observation.")
        self.held_for_freshness = True
        self.previous_stop_receipt = last

    def _hold_for_registration(self) -> None:
        """Require a hold with fresh stopped feedback, reconciled dose, and review pending."""
        for period in range(self.scenario.registration_review_periods):
            status = self._call(restart=period == 0)
            assert self.latest is not None
            if status != "waiting" or self.latest[1]["command"] is not None:
                raise _SubmissionError("Did not hold while the remounted part registration was under review.")
            self.registration_review_hold_packets += 1
            self.plant.advance()

    def run(self) -> None:
        """Execute a complete faulted mission or independently proven deadline block."""
        restart = False
        plant = self.plant
        for index, phase in enumerate(self.schedule):
            if index:
                self.scenario = phase
                self.moving_world = self._next_scene() if phase.world_update_during_motion else None
                self.interrupted_at = None
            self._await_fault(restart=restart)
            self._interrupt()
            restart = True
            if phase.registration_review_periods:
                self._hold_for_registration()
                # Install the follow-up capture while the spray interlock is disabled.
                plant.set_permit(False)
                self._call(scene=self._scene_update())
                plant.advance()
                plant.set_permit(True)
                restart = False
        if self.scenario.expect_blocked:
            # No material is delivered while waiting out the revoked mission.
            # At the deadline there is no feasible amount of future work.
            plant.now_ns = max(plant.now_ns, self.deadline)
            if self._call(restart=True) != "blocked":
                raise _SubmissionError("A stopped, reconciled and time-exhausted mission did not report blocked.")
            return
        while plant.now_ns <= self.deadline:
            if self._call(receipts=self._normal_receipts(), restart=restart) == "complete":
                if self.remount_revision is not None and not any(
                    epoch.revision >= self.remount_revision for epoch in self.issued_epochs.values()
                ):
                    raise _SubmissionError("The mission did not issue a fresh motion after remount.")
                return
            restart = False
            plant.advance()
        raise _SubmissionError("The live mission did not finish within the deadline.")

    def evidence(self, status: Literal["passed", "failed", "unresolved"], findings: tuple[str, ...]) -> LiveEvidence:
        """Return independent observed measurements while preserving unresolved status."""
        first = self.interruptions[0] if self.interruptions else None
        return LiveEvidence(status, findings, self.process.evidence(), self.plant.now_ns, len(self.authority),
                            self.stops, first.time_ns if first else None, first.readback_age_ns if first else None,
                            first.spray_permitted if first else None, first.scene_revision if first else None,
                            tuple(self.interruptions), self.minimum_clearance, self.clearance_count,
                            self.remount_motions, self.held_for_receipt, self.held_for_freshness,
                            self.registration_review_hold_packets, self.restarted,
                            self.cold_progress, self.plant.emitted_ml, self.plant.requested_ml,
                            self.plant.priming_suppressed_ml, self.plant.pressure_suppressed_ml,
                            tuple(self.plant.pressure_samples))


def audit_live(
    job: Mapping[str, Any], registration: Mapping[str, Any], runner: Runner, *, urdf: Path, srdf: Path,
    scenario: LiveScenario, max_process_step_ns: int = 5_000_000, max_cell_edge_m: float = 0.004,
    followups: tuple[LiveScenario, ...] = (),
) -> LiveEvidence:
    """Measure a submitted supervisor through native motion, receipts, and restart.

    The runner owns process isolation and its durable state directory. All
    scene, eligibility, and material measurements are verifier-owned. A
    nominal candidate policy, dose estimate, or assertion is never used
    as ground truth. The driver distinguishes an uncertifiable fixture
    from an observed submission failure.
    """
    mission = _Mission(job, registration, runner, urdf, srdf, scenario, max_process_step_ns, max_cell_edge_m,
                       followups=followups)
    try:
        mission.run()
        sag = scenario.pressure_sag
        if sag is not None and not math.isclose(mission.plant.pressure_suppressed_ml, sag.missing_ml, abs_tol=1e-9):
            raise _UnresolvedError("The mission did not exercise the full authored pressure loss.")
    except _SubmissionError as issue:
        return mission.evidence("failed", (str(issue),))
    except _UnresolvedError as issue:
        return mission.evidence("unresolved", (str(issue),))
    return mission.evidence("passed", ())
