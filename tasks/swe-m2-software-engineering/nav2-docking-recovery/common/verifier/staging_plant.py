"""Independent collision geometry and route-following plant for docking staging."""

from cmath import phase
from math import hypot, isfinite
from pathlib import Path
import json

from plant import Plant, Record, orient, require, scenario_config


def footprint_gap(spec: Record, z: complex, heading: float) -> float:
    """Measure a separation-axis gap by independently projecting body corner vertices."""
    length, width = [side + spec["margin_m"] for side in spec["footprint"]]
    polygon = [z + complex(x, y) * orient(heading) for x in (-length, length) for y in (-width, width)]
    left, low, right, high = spec["bounds"]
    bounding = min(min(p.real - left, right - p.real, p.imag - low, high - p.imag) for p in polygon)
    worst = bounding
    for x0, y0, x1, y1 in spec["obstacles"]:
        obstacle = [complex(x, y) for x in (x0, x1) for y in (y0, y1)]
        separations = []
        for axis in (1, 1j, orient(heading), 1j * orient(heading)):
            a = [(p / axis).real for p in polygon]
            b = [(p / axis).real for p in obstacle]
            separations.append(max(min(a) - max(b), min(b) - max(a)))
        worst = min(worst, max(separations))
    return worst


class StagingPlant(Plant):
    """Execute only observed twist commands and independently monitor room geometry."""

    def __init__(self, case: Record, config: Record) -> None:
        """Start in the inward area, with no permission to drive directly toward the dock."""
        super().__init__(case, config)
        self.nav = config["navigation"]
        self.edges = {edge["id"]: edge for edge in self.nav["edges"]}
        self.current = self.nav["start"]
        self.active = None
        self.offset = 0
        self.handoff: int | None = None
        self.travel_started: int | None = None
        self.chosen_edges: list[str] = []
        self.minimum_gap = footprint_gap(self.nav, self.position, self.yaw)
        self.paused = 0

    def contact(self) -> bool:
        """Only a robot that reached the docking approach can claim contact."""
        return self.handoff is not None and super().contact()

    def close_to(self, node: str) -> bool:
        """Compare actual chassis position with a commissioned named pose."""
        x, y, heading = self.nav["nodes"][node]
        return (abs(self.position - complex(x, y)) <= self.nav["position_tolerance_m"]
                and abs(phase(orient(self.yaw - heading))) <= self.nav["heading_tolerance_rad"])

    def observe(self, tick: int) -> Record:
        """Publish independent map position, lane holds and a post-staging visible tag."""
        output = super().observe(tick)
        if any(a <= tick < b for a, b in self.case.get("map_holes", [])):
            output["map_pose"] = None
            self.paused += 1
        else:
            output["map_pose"] = [self.position.real, self.position.imag, self.yaw]
        hold = set()
        for a, b, edges in self.case.get("holds", []):
            if a <= tick < b:
                hold.update(edges)
        output["blocked_edges"] = sorted(hold)
        if self.handoff is None:
            output["detections"] = []
            self.accepted_captures.clear()
            self.first_valid = None
        else:
            if not self.case.get("prestage_echo"):
                output["detections"] = [value for value in output["detections"] if value["tick"] >= self.handoff]
            self.accepted_captures = [stamp for stamp in self.accepted_captures if stamp >= self.handoff]
        return output

    def observe_command(self, response: Record, observation: Record) -> None:
        """Apply the staging command, checking continuity and allowing deliberate waits."""
        if self.handoff is not None:
            super().observe_command(response, observation)
            return
        v, w, status = response.get("v_mps"), response.get("w_radps"), response.get("status")
        require(all(type(x) in (int, float) and -1 <= x <= 1 and isfinite(x) for x in (v, w)),
                "invalid staging twist")
        at_staging = self.current == self.nav["staging"] and self.active is None
        require("stage_edge" in response or (at_staging and v == w == 0),
                "missing staging edge report before reaching the charger approach")
        edge_id = response.get("stage_edge")
        require(status in ("running", "failed") and (status == "running" or v == w == 0),
                "invalid staging status or nonstationary failure")
        if v == w == 0:
            require(edge_id in (None, self.active), "a stationary request granted a different edge")
            if at_staging:
                require(self.close_to(self.current), "requested staging handoff outside its measured pose")
                self.handoff = self.tick
            return
        require(observation["map_pose"] is not None and observation["odom"] is not None,
                "moved during a lost staging localization update")
        require(edge_id in self.edges, "requested an untaught staging edge")
        edge = self.edges[edge_id]
        if self.active is None:
            require(edge_id not in observation["blocked_edges"], "entered an externally held lane")
            require(edge["source"] == self.current and self.close_to(self.current),
                    "entered a directed edge away from its measured start pose")
            self.active = edge_id
            self.chosen_edges.append(edge_id)
        require(edge_id == self.active, "abandoned an unfinished motion primitive")
        if self.travel_started is None:
            self.travel_started = self.tick
        step = self.offset
        for segment in edge["segments"]:
            if step < segment["ticks"]:
                require(abs(v-segment["v_mps"]) <= 1e-9 and abs(w-segment["w_radps"]) <= 1e-9,
                        "did not follow the authorized navigation primitive")
                break
            step -= segment["ticks"]
        require(-self.nav["reverse_max_mps"] <= v <= self.nav["forward_max_mps"]
                and abs(w) <= self.nav["angular_max_radps"], "staging primitive exceeded configured bounds")
        self.integrate(v, w)
        self.offset += 1
        if self.offset == sum(segment["ticks"] for segment in edge["segments"]):
            self.current = edge["target"]
            require(self.close_to(self.current), "motion did not converge to its commissioned target")
            self.active = None
            self.offset = 0

    def integrate(self, v: float, w: float) -> None:
        """Certify the observed sweep with an independent dense rigid-travel bound."""
        duration = self.config["tick_seconds"]
        initial = self.position
        radius = hypot(*(side + self.nav["margin_m"] for side in self.nav["footprint"]))
        speed = abs(v) + radius * abs(w)
        for samples in (15, 60, 240):
            gap_for_step = float("inf")
            for index in range(samples + 1):
                elapsed = duration * index / samples
                rotation = orient(w * elapsed)
                next_pos = (initial + v * elapsed * orient(self.yaw) if abs(w) < 1e-10 else
                            initial + (v / (1j * w)) * orient(self.yaw) * (rotation - 1))
                gap = footprint_gap(self.nav, next_pos, self.yaw + w * elapsed)
                gap_for_step = min(gap_for_step, gap)
                require(gap > 0.0, "actual swept chassis entered a geometry obstacle or corridor boundary")
                if self.handoff is not None:
                    require(next_pos.real >= -0.027, "vehicle exceeded connector penetration limit")
            if gap_for_step > speed * duration / (2 * samples):
                break
        else:
            require(False, "continuous chassis clearance could not be established")
        self.minimum_gap = min(self.minimum_gap, gap_for_step)
        self.position = next_pos
        self.yaw = phase(orient(self.yaw + w * duration))


def drive_case(app: Path, root: Path, case: Record, driver_type: type) -> Record:
    """Run the v2 controller from untaken route through verified service."""
    root.mkdir(mode=0o755)
    state = root / "state"
    state.mkdir()
    state.chmod(0o777)
    case = case | {"pose": case["navigation"]["nodes"][case["navigation"]["start"]]}
    configuration = scenario_config(case) | {"navigation": case["navigation"], "tag_id": case["tag"]}
    config_path = root / "config.json"
    config_path.write_text(json.dumps(configuration))
    plant = StagingPlant(case, configuration)
    driver = driver_type(app, config_path, state)
    restarted = False
    terminal, end_tick = None, None
    try:
        for tick in range(configuration["deadline_tick"] + 3):
            observation = plant.observe(tick)
            response = driver.exchange(observation)
            plant.observe_command(response, observation)
            if tick == case.get("restart_at"):
                driver.restart()
                require(driver.exchange(observation) == response, "lost staging reply did not replay after restart")
                restarted = True
            if response["status"] in ("failed", "docked"):
                if terminal is None:
                    terminal, end_tick = response["status"], tick
                else:
                    require(response["status"] == terminal, "terminal outcome changed after the controller stopped")
            elif terminal is not None:
                require(False, "terminal staging mission resumed motion")
            if end_tick is not None and tick == end_tick + 2:
                break
        expected = case.get("expected", "docked")
        require(terminal == expected, f"expected {expected}; got {terminal}; staging={plant.handoff}; contacts={plant.contacts}")
        if case.get("no_staging"):
            require(plant.handoff is None and not plant.chosen_edges and not plant.contacts and end_tick <= configuration["deadline_tick"],
                    "impossible mission attempted motion or failed to stop")
        else:
            require(plant.handoff is not None and plant.chosen_edges and plant.completed, "no physical staged docking progress")
            require(len(plant.contacts) == case.get("contact_count", 1), "incorrect physical charge attempt count")
        if case.get("required_edge"):
            require(case["required_edge"] in plant.chosen_edges, "the staged route did not traverse an available required aisle")
        if case.get("minimum_wait") is not None:
            require(plant.travel_started is not None and plant.travel_started >= case["minimum_wait"],
                    "entered the held aisle before it opened")
        return {"staged_at": plant.handoff, "finish_tick": end_tick, "route": plant.chosen_edges,
                "contact_ticks": plant.contacts, "restart": restarted, "pause_ticks": plant.paused,
                "minimum_gap_m": round(plant.minimum_gap, 7), "end_status": terminal}
    finally:
        driver.close()
