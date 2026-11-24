"""Author fixtures and independently evaluate public CLI outputs."""

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import math
from pathlib import Path


def write(path, value):
    path.write_text(json.dumps(value, allow_nan=False) + "\n", encoding="utf-8")
    return path


def read(path):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > 1_000_000:
        raise ValueError("Expected a small regular JSON output")
    return json.loads(path.read_text(encoding="utf-8"))


def geometry(width=8, height=6, resolution=1.0, origin=(0, 0)):
    return {"width": width, "height": height, "resolution_m": resolution, "origin_m": list(origin)}


def map_doc(cells, **dimensions):
    return {"schema_version": 1, **geometry(**dimensions),
            "cells": [[c, r, state] for (c, r), state in sorted(cells.items(), key=lambda entry: entry[0][::-1])]}


def scan(pose, *beams):
    return {"pose": list(pose), "beams": list(beams)}


def build_fixture(run, root):
    grid = write(root / "grid.json", geometry())
    visit = write(root / "visit.json", {"id": "test-visit", "scans": [
        scan((0.5, 0.5, 0), (0, 3, True)),
        scan((4.5, 0.5, math.pi), (0, 4, False)),
        scan((-0.5, 2.5, 0), (0, 3, True)),
        scan((0.5, 1.5, math.pi / 4), (0, math.sqrt(18), False)),
        scan((0.5, 5.0, 0), (0, 5, False)),
        scan((7.5, 3.5, 0), (0, 0.5, True)),
    ]})
    out, repeated = root / "map.json", root / "again.json"
    base = ("build", "--grid", grid, "--visit", visit, "--output")
    if run(*base, out).returncode:
        return dict(geometry=False, deterministic=False, rejects_bad_visit=False)
    expected = map_doc({
        (0, 0): "free", (1, 0): "free", (2, 0): "free", (3, 0): "occupied",
        (4, 0): "free", (0, 2): "free", (1, 2): "free", (2, 2): "occupied",
        (0, 1): "free", (2, 3): "free", (3, 4): "free", (7, 3): "free",
    })
    actual = read(out)
    repeat_ok = not run(*base, repeated).returncode and repeated.read_bytes() == out.read_bytes()
    write(visit, {"id": "invalid", "scans": [scan((0.5, 0.5, 0), (0, -1, True))]})
    before = out.read_bytes()
    rejects = run(*base, out).returncode != 0 and out.read_bytes() == before
    return {"geometry": actual == expected, "deterministic": repeat_ok, "rejects_bad_visit": rejects}


def through_inverse(x, y, transform):
    tx, ty, yaw = transform
    ca, sa = math.cos(yaw), math.sin(yaw)
    return ca * (x - tx) + sa * (y - ty), -sa * (x - tx) + ca * (y - ty)


def forward(x, y, transform):
    tx, ty, yaw = transform
    ca, sa = math.cos(yaw), math.sin(yaw)
    return tx + ca * x - sa * y, ty + sa * x + ca * y


def registration_visit(positions, transform):
    observations = []
    local_points = []
    for i, (x, y) in enumerate(positions):
        endpoint = through_inverse(x, y, transform)
        sensor_x, sensor_y = ((0.2, -0.5), (0.6, -0.3))[i % 2]
        sensor_yaw = 0.11 * (i % 4) - 0.1
        dx, dy = endpoint[0] - sensor_x, endpoint[1] - sensor_y
        observations.append(scan((sensor_x, sensor_y, sensor_yaw),
                                 (math.atan2(dy, dx) - sensor_yaw, math.hypot(dx, dy), True),
                                 (0.0, 0.5, False)))
        local_points.append(endpoint)
    result = {"id": "unsurveyed", "scans": observations}
    return result, local_points


def register_fixture(run, root):
    # Sparse angularly asymmetric wall junctions. Independent endpoints are built from known placements.
    cells = [(3, 4), (4, 12), (7, 18), (13, 5), (16, 15), (19, 22), (24, 6),
             (27, 13), (30, 19), (8, 24), (25, 26), (32, 9)]
    centers = [((c + 0.5) * 0.1, (r + 0.5) * 0.1) for c, r in cells]
    truth = (0.44, -0.18, -0.11)
    visit_doc, endpoints = registration_visit(centers + [(8.45, 8.1), (-6.0, -5.0)], truth)
    grid_size = dict(width=70, height=45, resolution=0.1)
    map_file = write(root / "map.json", map_doc({cell: "occupied" for cell in cells}, **grid_size))
    visit = write(root / "visit.json", visit_doc)
    prior = write(root / "prior.json", {"center": [0.77, 0.15, math.tau + 0.07],
                                       "xy_radius_m": 0.58, "yaw_radius_rad": 0.34})
    output = root / "report.json"

    def run_registration():
        if run("register", "--map", map_file, "--visit", visit, "--prior", prior, "--output", output).returncode:
            return {}
        return read(output)

    report = run_registration()
    pose = report.get("world_from_visit")
    if not isinstance(pose, list) or len(pose) != 3:
        fit = False
        correct_support = False
    else:
        x, y, yaw = pose
        fit = (report.get("status") == "ok" and math.dist((x, y), truth[:2]) <= 0.13
               and abs(math.remainder(yaw - truth[2], math.tau)) <= 0.08
               and abs(x - 0.77) <= 0.58 and abs(y - 0.15) <= 0.58 and abs(yaw - math.tau - 0.07) <= 0.34)
        count = sum(min(math.dist(forward(*point, pose), center) for center in centers) <= 0.12
                    for point in endpoints)
        correct_support = (count >= 10 and report.get("hit_endpoints") == 14
                           and report.get("supported_endpoints") == count
                           and math.isclose(report.get("coverage", -1), count / 14, abs_tol=1e-9))

    repeated = cells + [(c + 23, r) for c, r in cells]
    write(map_file, map_doc({cell: "occupied" for cell in repeated}, **grid_size))
    write(visit, registration_visit(centers, (0.0, 0.0, 0.0))[0])
    write(prior, {"center": [1.15, 0.02, 0.04], "xy_radius_m": 1.25, "yaw_radius_rad": 0.19})
    ambiguous = run_registration()
    ambiguous_ok = (ambiguous.get("status") == "ambiguous" and ambiguous.get("world_from_visit") is None
                    and ambiguous.get("supported_endpoints") == 12 and ambiguous.get("hit_endpoints") == 12
                    and ambiguous.get("coverage") == 1.0)

    write(visit, registration_visit([(22, 18), (31, 22), (40, -17), (13, 19), (20, 21), (22, 25)],
                                    truth)[0])
    failure = run_registration()
    insufficient = (failure.get("status") == "insufficient_support" and failure.get("world_from_visit") is None
                    and failure.get("supported_endpoints") == 0 and failure.get("hit_endpoints") == 6
                    and failure.get("coverage") == 0.0)
    return {"registration": fit, "endpoint_denominator": correct_support,
            "repeated_geometry": ambiguous_ok, "insufficient_support": insufficient}


def visit_observations(name, transform, evidence):
    observations = []
    for (col, row), hit in evidence:
        x, y = through_inverse(col + 0.2, row + 0.5, transform)
        observations.append(scan((x, y, -transform[2]), (0.0, 0.38, hit)))
    return {"id": name, "scans": observations}


def evidence_fixture(run, root):
    base = write(root / "base.json", map_doc({
        (4, 1): "occupied", (2, 1): "free", (6, 1): "free", (1, 4): "occupied", (3, 4): "occupied",
    }))
    certain = [((4, 1), False), ((2, 1), True), ((1, 4), False), ((7, 5), False), ((0, 3), True)]
    groups = [
        ("visit-b", (0.35, -0.2, 0.17), certain + [((6, 3), True)]),
        ("visit-c", (0.0, 0.3, -0.2), [((0, 3), False)]),
        ("visit-a", (-0.4, 0.72, -0.24), certain + [((6, 1), True), ((6, 3), True), ((6, 3), False)]),
    ]
    provenance = []
    for name, transform, observations in groups:
        write(root / (name + ".json"), visit_observations(name, transform, observations))
        provenance.append({"visit": name + ".json", "world_from_visit": transform})
    evidence = write(root / "visits.json", {"visits": provenance, "protected_cells": [[1, 4]]})
    patch = root / "patch.json"
    arguments = ("propose", "--base", base, "--evidence", evidence, "--output")
    if run(*arguments, patch).returncode:
        return dict(stable_changes=False, vetoes=False, deterministic=False, rejects_duplicate_visits=False)
    result = read(patch)
    original = base.read_bytes()
    expected_changes = [
        {"cell": [2, 1], "from": "free", "to": "occupied", "support": ["visit-a", "visit-b"]},
        {"cell": [4, 1], "from": "occupied", "to": "free", "support": ["visit-a", "visit-b"]},
        {"cell": [7, 5], "from": "unknown", "to": "free", "support": ["visit-a", "visit-b"]},
    ]
    actual_changes = result.get("changes", [])
    positive = (result.get("schema_version") == 1 and result.get("base_sha256") == hashlib.sha256(original).hexdigest()
                and [entry for entry in actual_changes if entry.get("cell") in [[2, 1], [4, 1], [7, 5]]]
                == expected_changes and base.read_bytes() == original)
    vetoes = positive and len(actual_changes) == len(expected_changes)
    before = patch.read_bytes()
    alternate = root / "alternate.json"
    write(evidence, {"visits": list(reversed(provenance)), "protected_cells": [[1, 4]]})
    repeat = not run(*arguments, alternate).returncode and alternate.read_bytes() == before
    write(evidence, {"visits": provenance + [provenance[0]], "protected_cells": []})
    rejects = run(*arguments, patch).returncode != 0 and patch.read_bytes() == before
    return {"stable_changes": positive, "vetoes": vetoes, "deterministic": repeat,
            "rejects_duplicate_visits": rejects}


def release_fixture(run, root):
    def receipt(*args):
        current = run(*args)
        return {} if current.returncode else json.loads(current.stdout)
    store = root / "store"
    status = {"init_and_pin": False, "publish_without_activation": False, "rejects_invalid_patch": False,
              "concurrent_compare_and_swap": False, "rollback_and_pinned_reads": False}
    base = root / "base.json"
    base.write_text(json.dumps(map_doc({(1, 1): "occupied", (3, 1): "free"}), indent=2) + "\n")
    original = base.read_bytes()
    base_id = hashlib.sha256(original).hexdigest()

    if receipt("init", "--store", store, "--map", base) != {"version": base_id, "active_version": base_id}:
        return status

    def read_snapshot(version, name):
        out = root / name
        current = run("snapshot", "--store", store, "--version", version, "--output", out)
        return out.read_bytes() if current.returncode == 0 and out.is_file() and not out.is_symlink() else b""

    status["init_and_pin"] = read_snapshot(base_id, "pinned-base.json") == original

    patch_doc = {"schema_version": 1, "base_sha256": base_id, "changes": [
        {"cell": [1, 1], "from": "occupied", "to": "free", "support": ["a", "b"]},
    ]}
    patch = write(root / "patch.json", patch_doc)
    initial = receipt("publish", "--store", store, "--base", base_id, "--patch", patch)
    first = initial.get("version")
    if not isinstance(first, str) or first == base_id:
        return status
    payload = read_snapshot(first, "pinned-first.json")
    status["publish_without_activation"] = (
        bool(payload) and hashlib.sha256(payload).hexdigest() == first
        and json.loads(payload) == map_doc({(1, 1): "free", (3, 1): "free"})
        and initial.get("active_version") == base_id and read_snapshot("active", "still-original.json") == original
        and receipt("publish", "--store", store, "--base", base_id, "--patch", patch) == initial)

    invalid_results = []
    for invalid in (
        {**patch_doc, "base_sha256": first},
        {**patch_doc, "changes": [dict(patch_doc["changes"][0], support=["a", "a"])]},
        {**patch_doc, "changes": [dict(patch_doc["changes"][0], **{"from": "free"})]},
        {**patch_doc, "changes": patch_doc["changes"] * 2},
    ):
        write(patch, invalid)
        invalid_results.append(run("publish", "--store", store, "--base", base_id, "--patch", patch).returncode != 0)
    status["rejects_invalid_patch"] = all(invalid_results) and read_snapshot("active", "after-failure.json") == original

    write(patch, {**patch_doc, "changes": [
        {"cell": [3, 1], "from": "free", "to": "occupied", "support": ["a", "b"]},
    ]})
    second = receipt("publish", "--store", store, "--base", base_id, "--patch", patch).get("version")
    if not isinstance(second, str) or second in (base_id, first):
        return status

    def activate(version, expect):
        return run("activate", "--store", store, "--version", version, "--expect-active", expect)

    with ThreadPoolExecutor(max_workers=2) as concurrent:
        requests = [concurrent.submit(activate, version, base_id) for version in (first, second)]
        succeeded = [version for version, request in zip((first, second), requests) if request.result().returncode == 0]
    if len(succeeded) != 1:
        return status
    winner = succeeded[0]
    after = read_snapshot("active", "active-raced.json")
    status["concurrent_compare_and_swap"] = hashlib.sha256(after).hexdigest() == winner
    second_bytes = read_snapshot(second, "second-before-rollback.json")
    rollback = activate(base_id, winner)
    status["rollback_and_pinned_reads"] = (
        not rollback.returncode and read_snapshot("active", "active-rolled-back.json") == original
        and read_snapshot(first, "first-after-rollback.json") == payload
        and bool(second_bytes) and read_snapshot(second, "second-after-rollback.json") == second_bytes)
    return status


def hit_distance(px, py, dx, dy, rectangles, maximum):
    """Trace one lidar beam against the first visible scene surface."""
    closest = maximum
    for xmin, ymin, xmax, ymax in rectangles:
        near, far = 0.0, closest
        for position, change, upper, lower in ((px, dx, xmax, xmin), (py, dy, ymax, ymin)):
            if abs(change) < 1e-12:
                if not lower <= position <= upper:
                    break
                continue
            first, second = sorted(((lower - position) / change, (upper - position) / change))
            near, far = max(near, first), min(far, second)
        else:
            if 0 < near <= far:
                closest = near
    return closest, closest < maximum


def survey(name, poses, rectangles, world_from_visit, angle_bias):
    """Simulate a multi-position lidar traversing a small indoor hall."""
    scans = []
    for x, y, heading in poses:
        local_x, local_y = through_inverse(x, y, world_from_visit)
        rays = []
        for direction in range(42):
            angle = direction * math.tau / 42 + angle_bias
            distance, hit = hit_distance(x, y, math.cos(heading + angle), math.sin(heading + angle), rectangles, 5.2)
            rays.append((angle, distance, hit))
        scans.append(scan((local_x, local_y, heading - world_from_visit[2]), *rays))
    return {"id": name, "scans": scans}


def hall_fixture(run, root):
    """Build a surveyed baseline, relocalize after furniture changes, and pin a released version."""
    rectangles = [
        (-0.1, -0.12, 8.04, 0.03), (-0.1, 4.92, 8.04, 5.12),
        (-0.12, -0.1, 0.03, 5.1), (7.92, -0.1, 8.1, 5.1),
        (1.13, 2.2, 1.43, 3.7), (5.1, 0.98, 5.45, 1.37),
        (6.31, 3.32, 6.58, 4.1), (4.4, 2.9, 4.69, 3.33),
        (2.33, 4.2, 3.19, 4.52),
    ]
    survey_poses = [(1.55, 0.7, 0.12), (2.25, 1.3, -0.18), (1.91, 2.6, 0.24),
                    (3.85, 1.83, 0.4), (4.94, 2.45, -0.65), (6.5, 1.5, 0.76), (5.1, 3.96, 0.31)]
    shifted_poses = [(1.41, 0.67, 0.17), (2.21, 1.36, -0.15), (1.87, 2.68, 0.21),
                     (3.82, 1.89, 0.43), (4.89, 2.40, -0.68), (6.45, 1.57, 0.79), (5.06, 3.9, 0.35)]
    pose = (0.51, -0.35, 0.23)
    grid = write(root / "grid.json", geometry(92, 62, 0.10, (-0.5, -0.5)))
    original_visit = write(root / "survey.json", survey("hall-survey", survey_poses, rectangles, (0, 0, 0), 0.0))
    subsequent_visit = write(
        root / "relocation.json",
        survey("hall-relocation", shifted_poses, rectangles[:-1] + [(3.22, 2.1, 3.55, 2.4)], pose, 0.015),
    )
    prior = write(root / "prior.json", {"center": [0.16, -0.05, 0.04], "xy_radius_m": 0.52, "yaw_radius_rad": 0.25})
    baseline = root / "baseline.json"
    registration = root / "fit.json"
    checks = {"hall_registration": False, "release_preserves_survey": False}
    if (run("build", "--grid", grid, "--visit", original_visit, "--output", baseline).returncode
            or run("register", "--map", baseline, "--visit", subsequent_visit, "--prior", prior,
                   "--output", registration).returncode):
        return checks
    solution = read(registration)
    recovered = solution.get("world_from_visit")
    checks["hall_registration"] = (
        solution.get("status") == "ok" and isinstance(recovered, list) and len(recovered) == 3
        and math.dist(recovered[:2], pose[:2]) <= 0.12 and abs(recovered[2] - pose[2]) <= 0.06
        and solution.get("hit_endpoints") > 200 and solution.get("coverage", 0) >= 0.65
    )
    value = read(baseline)
    if len(value.get("cells", [])) <= 1000:
        return checks
    releases = root / "releases"
    digest = hashlib.sha256(baseline.read_bytes()).hexdigest()
    created = run("init", "--store", releases, "--map", baseline)
    pinned = root / "pinned.json"
    if created.returncode or run("snapshot", "--store", releases, "--version", digest,
                                  "--output", pinned).returncode:
        return checks
    checks["release_preserves_survey"] = baseline.read_bytes() == pinned.read_bytes()
    return checks


GROUPS = (build_fixture, register_fixture, evidence_fixture, release_fixture, hall_fixture)
