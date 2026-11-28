"""Generate the Downtown plan in the city-plan/1 format.

Author tool (never packaged). The format is defined in common/design/plan/FORMAT.md.
Downtown is about 0.86 x 0.87 km: an 8 x 8 junction grid with uneven spacing and 7 x 7
blocks, mixed road classes (arterials, two-way streets, one-way streets), signalised and
all-way-stop junctions, parcels with zoning and interiors, the points of interest the
missions and shops use, and two highways that leave the map at portal nodes: east to Ashby
Port and north, through an S-curve, to Sable Hills.

The central 4 x 4 junctions are the Downtown core block. Its random values (signal offsets,
parcel splits, building heights) are drawn first, in the same order as when the core was
the whole map, so its parcels and points of interest keep their places; everything else
draws from its own generator keyed by its id, so editing one block changes nothing else.
--seed only draws heights, splits, zonings and signal offsets; the output never names it.

--layout random lays out another Downtown, the kind of plan a level designer tries through
--plan-dir (GDD WD-8), from a draw (--draw N, or --draw-file FILE holding {"draw": N}):
- the grid: 7 to 9 lines each way with drawn spacing, no line within 6 m of a line of the
  default layout (so no junction keeps its place), 0.69 to 0.82 km from the first line to
  the last (the default layout's are 0.75 and 0.73 km);
- the roads: one or two arterials each way, up to two one-way streets each way with drawn
  directions, streets on the map's edge; drawn lane widths and speed limits per line; some
  junctions of streets signalised; every signal program (greens per approach, walk, amber,
  all-red, offset) drawn;
- the highways: from drawn arterials to the same portal nodes (pt_east, pt_north) on the
  map's edge, with the default layout's lanes; drawn lengths and a drawn S-curve north;
- the blocks: drawn sidewalk widths; drawn splits (whole, halves, quarters, sixths),
  zonings, heights and setbacks;
- the core: 3 x 3 drawn blocks holding the plaza, the turf, the givers, the R1 lap round
  its perimeter (direction and start side drawn, never longer than the default lap) and
  the points of interest on drawn parcels with drawn doors and rooms.
Every point-of-interest id (and kind), portal node id and link stays the default layout's;
every other id may name another place. The draw fixes everything and the plan never names
it. A drawn plan is checked with scripts/check_plan.py (format and GDD ids) before it is
written.

Usage:
  python scripts/gen_plan.py --out common/design/plan/downtown.json
  python scripts/gen_plan.py --layout random --draw-file FILE --out DIR/downtown.json
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
import random
import sys
from dataclasses import dataclass
from pathlib import Path

FORMAT = "city-plan/1"
CURB_M = 0.15
SIDEWALK_W = 3.0
SETBACK_M = 3.0
CROSSWALK_GAP_M = 0.5
CROSSWALK_W = 3.0
STOP_GAP_M = 1.0

# Road classes: lanes per direction (one-way: total lanes), lane width, speed limit.
ROAD = {
    "arterial": {"lanes": 2, "width": 3.5, "speed": 50, "oneway": False},
    "street": {"lanes": 1, "width": 3.25, "speed": 40, "oneway": False},
    "oneway": {"lanes": 2, "width": 3.25, "speed": 40, "oneway": True},
    "highway": {"lanes": 2, "width": 3.75, "speed": 90, "oneway": False},
}
CLASS_NAME = {
    "arterial": "arterial",
    "street": "street",
    "oneway": "street",
    "highway": "highway",
}
RANK = {"highway": 3, "arterial": 2, "oneway": 1, "street": 1}

# Columns run north-south (constant x), rows run east-west (constant z). Row 0 is north.
XS = [-380.0, -290.0, -190.0, -70.0, 60.0, 180.0, 280.0, 370.0]
ZS = [-370.0, -280.0, -180.0, -60.0, 50.0, 170.0, 270.0, 360.0]
COL_CLASS = [
    "street",
    "street",
    "street",
    "arterial",
    "street",
    "street",
    "oneway",
    "street",
]
ROW_CLASS = [
    "street",
    "street",
    "street",
    "oneway",
    "arterial",
    "street",
    "street",
    "street",
]
CORE = range(2, 6)  # the core's columns and rows (junction indices)
CORE_BLOCKS = range(2, 5)  # the core's blocks

# The highways: from a grid junction to a portal node on the map's edge.
EAST_FROM = (7, 4)  # the arterial row 4 continues east
NORTH_FROM = (3, 0)  # the arterial column 3 continues north
EAST_LEN = 70.0
NORTH_STRAIGHT = 15.0  # straight run before the S-curve and after it
NORTH_RADIUS = 60.0
NORTH_TURN_DEG = 35.0
MARGIN = 40.0

ZONING = {
    "commercial": [14.0, 60.0],
    "residential": [9.0, 30.0],
    "civic": [10.0, 22.0],
    "industrial": [6.0, 14.0],
    "plaza": [0.0, 0.0],
    "park": [0.0, 0.0],
    "parking": [0.0, 0.0],
}
BUILT = {"commercial", "residential", "civic", "industrial"}

# Parcel zoning of the core's blocks (core block indices), quadrants NW, NE, SW, SE. A
# single entry means one parcel covers the block.
CORE_ZONING = {
    (0, 0): ["residential", "residential", "commercial", "residential"],
    (1, 0): ["commercial", "residential", "commercial", "commercial"],
    (2, 0): ["civic", "residential", "residential", "commercial"],
    (0, 1): ["commercial", "parking", "commercial", "commercial"],
    (1, 1): ["plaza"],
    (2, 1): ["civic", "commercial", "commercial", "commercial"],
    (0, 2): ["commercial", "parking", "residential", "residential"],
    (1, 2): ["civic", "commercial", "commercial", "parking"],
    (2, 2): ["parking", "commercial", "residential", "parking"],
}
# Outer blocks draw one of their area's layouts.
OUTER_ZONING = {
    "residential": [
        ["residential", "residential", "residential", "residential"],
        ["residential", "park", "residential", "residential"],
        ["residential", "residential", "civic", "parking"],
        ["park"],
    ],
    "east": [
        ["industrial", "commercial", "industrial", "parking"],
        ["commercial", "industrial", "parking", "industrial"],
        ["commercial", "commercial", "parking", "commercial"],
    ],
}
QUADS = ["NW", "NE", "SW", "SE"]

# Points of interest placed on core parcels: (core block, quadrant) -> spec.
PARCEL_POIS = {
    ((0, 0), "NW"): {
        "id": "safehouse_downtown",
        "kind": "safehouse",
        "room": (8.0, 8.0),
    },
    ((0, 0), "SW"): {"id": "shop_food_downtown", "kind": "shop", "shop": "food"},
    ((1, 0), "NW"): {"id": "shop_clothes_downtown", "kind": "shop", "shop": "clothes"},
    ((2, 0), "NW"): {"id": "hospital_downtown", "kind": "hospital"},
    ((0, 1), "NW"): {"id": "shop_weapons_downtown", "kind": "shop", "shop": "weapons"},
    ((0, 1), "NE"): {"id": "garage_downtown", "kind": "garage"},
    ((2, 1), "NW"): {"id": "bank_downtown", "kind": "bank"},
    ((0, 2), "NE"): {"id": "d1_pickup", "kind": "mission_point"},
    ((1, 2), "NW"): {"id": "police_station_downtown", "kind": "police_station"},
    ((1, 2), "SE"): {"id": "h1_car", "kind": "mission_point"},
    ((2, 2), "NW"): {"id": "h1_stash", "kind": "mission_point"},
    ((2, 2), "SE"): {"id": "d1_dropoff", "kind": "mission_point"},
}

# A drawn layout (--layout random). Grid gaps by line count, the extent, the core's lap.
DRAWN_GAPS = {7: (112.0, 148.0), 8: (96.0, 132.0), 9: (84.0, 118.0)}
DRAWN_EXTENT_M = (690.0, 820.0)
DRAWN_LAP_M = (1000.0, 1440.0)  # R1's lap: never longer than the default layout's
DRAWN_CLEAR_M = 6.0  # no drawn grid line within this of a line of the default layout
DRAWN_WIDTH = {
    "street": (3.0, 3.25, 3.5),
    "arterial": (3.25, 3.5, 3.75),
    "oneway": (3.0, 3.25, 3.5),
}
DRAWN_SPEED = {"street": (30, 40), "arterial": (50, 60), "oneway": (40, 50)}
DRAWN_SIGNAL_SHARE = 0.25  # four-way junctions of streets that get signals
# Block splits and parcel zonings by area, with their weights.
DRAWN_SPLITS = {
    "core": (("quads", 5), ("sixths", 3), ("halves", 3)),
    "residential": (("quads", 4), ("halves", 3), ("sixths", 2), ("whole", 2)),
    "east": (("quads", 4), ("halves", 3), ("sixths", 2), ("whole", 1)),
}
DRAWN_ZONES = {
    "core": (
        ("commercial", 9),
        ("residential", 4),
        ("civic", 2),
        ("parking", 4),
        ("park", 1),
    ),
    "residential": (
        ("residential", 12),
        ("park", 3),
        ("civic", 2),
        ("parking", 2),
        ("commercial", 1),
    ),
    "east": (("industrial", 8), ("commercial", 6), ("parking", 4), ("residential", 2)),
}
DRAWN_WHOLE = {
    "residential": ("park", "park", "civic"),
    "east": ("industrial", "parking", "park"),
}
# The points of interest on core parcels (PARCEL_POIS's specs), the zoning each needs, the
# order they are placed in (biggest buildings first), pairs kept in different blocks.
SPECS = {spec["id"]: spec for spec in PARCEL_POIS.values()}
POI_ZONING = {
    "bank": "civic",
    "shop": "commercial",
    "safehouse": "residential",
    "hospital": "civic",
    "police_station": "civic",
    "garage": "parking",
    "mission_point": "parking",
}
DRAWN_ORDER = sorted(SPECS, key=lambda i: (list(POI_ZONING).index(SPECS[i]["kind"]), i))
APART = {"d1_dropoff": "d1_pickup", "h1_stash": "h1_car"}
SIDES = ("N", "E", "S", "W")


@dataclass
class Layout:
    """The shape of one Downtown.

    Columns run north-south (constant x) and rows east-west (constant z); row 0 is north.
    Classes, lane widths and speed limits are per line; a flipped one-way column runs north
    and a flipped one-way row runs west (south and east otherwise). The core is 4 x 4
    junctions (3 x 3 blocks). north_turn_deg is the S-curve's first turn (negative turns
    left). The plaza, turf and giver blocks are (column, row) block indices; a giver is
    (block, side of its sidewalk ring, fraction along that side); lap is (clockwise, start
    side as an index into SIDES); band is (column, first row, last row) of the core
    district. drawn is False for the default layout, whose blocks, parcels and signal
    programs follow the tables above, and True for a drawn one, which draws them too.
    """

    xs: list
    zs: list
    col_class: list
    row_class: list
    col_width: list
    row_width: list
    col_speed: list
    row_speed: list
    col_flip: list
    row_flip: list
    core_c: range
    core_r: range
    east_from: tuple
    north_from: tuple
    east_len: float
    north_straight: float
    north_radius: float
    north_turn_deg: float
    margin: float
    plaza_block: tuple
    plaza_heading: float
    delivery_offset: tuple
    delivery_heading: float
    race_giver: tuple
    heist_giver: tuple
    turf_block: tuple
    lap: tuple
    band: tuple
    drawn: bool = False

    @property
    def core_bc(self) -> range:
        return range(self.core_c.start, self.core_c.stop - 1)

    @property
    def core_br(self) -> range:
        return range(self.core_r.start, self.core_r.stop - 1)

    def col_half(self, c):
        return half_of(self.col_class[c], self.col_width[c])

    def row_half(self, r):
        return half_of(self.row_class[r], self.row_width[r])


def default_layout() -> Layout:
    """The shipped Downtown."""
    lo = min(CORE_BLOCKS)
    return Layout(
        xs=XS,
        zs=ZS,
        col_class=COL_CLASS,
        row_class=ROW_CLASS,
        col_width=[ROAD[c]["width"] for c in COL_CLASS],
        row_width=[ROAD[c]["width"] for c in ROW_CLASS],
        col_speed=[ROAD[c]["speed"] for c in COL_CLASS],
        row_speed=[ROAD[c]["speed"] for c in ROW_CLASS],
        col_flip=[False] * len(XS),
        row_flip=[False] * len(ZS),
        core_c=CORE,
        core_r=CORE,
        east_from=EAST_FROM,
        north_from=NORTH_FROM,
        east_len=EAST_LEN,
        north_straight=NORTH_STRAIGHT,
        north_radius=NORTH_RADIUS,
        north_turn_deg=-NORTH_TURN_DEG,
        margin=MARGIN,
        plaza_block=(lo + 1, lo + 1),
        plaza_heading=0.0,
        delivery_offset=(12.0, -8.0),
        delivery_heading=270.0,
        race_giver=((lo + 1, lo), 0, 0.5),
        heist_giver=((lo, lo + 2), 0, 0.5),
        turf_block=(lo, lo + 2),
        lap=(True, 0),
        band=(lo, lo + 1, lo + 4),
    )


def nid(c, r):
    return f"j_{c}{r}"


def heading_of(dx, dz):
    """Heading in degrees clockwise from north (-z) of a horizontal direction."""
    return round(math.degrees(math.atan2(dx, -dz)) % 360.0, 3)


def half_of(cls, width):
    """How far a road of this class and lane width reaches from its centreline."""
    spec = ROAD[cls]
    if spec["oneway"]:
        return spec["lanes"] * width / 2.0
    return spec["lanes"] * width


def keyed(seed, *key):
    """A generator of its own for one part of the map."""
    return random.Random(f"{seed}:" + ":".join(str(k) for k in key))


def is_core_node(lay, c, r):
    return c in lay.core_c and r in lay.core_r


def r3(v):
    return round(v, 3)


def halves(v):
    """v rounded to the nearest 0.5."""
    return round(v * 2.0) / 2.0


def pick(g, table):
    """A weighted choice from ((value, weight), ...)."""
    return g.choices([v for v, _ in table], [w for _, w in table])[0]


# ------------------------------------------------------------------ a drawn layout
def drawn_lines(g, n, default):
    """n grid line positions, centred near 0; None when they break the limits."""
    lo, hi = DRAWN_GAPS[n]
    gaps = [halves(g.uniform(lo, hi)) for _ in range(n - 1)]
    total = sum(gaps)
    lines = [halves(-total / 2.0 + g.uniform(-30.0, 30.0))]
    for gap in gaps:
        lines.append(lines[-1] + gap)
    if not DRAWN_EXTENT_M[0] <= total <= DRAWN_EXTENT_M[1]:
        return None
    if any(abs(v - d) < DRAWN_CLEAR_M for v in lines for d in default):
        return None
    return lines


def drawn_classes(g, n, core0):
    """Streets on the map's edge, one or two arterials inside, up to two one-way streets
    off the core's perimeter (R1 laps it, so it stays two-way)."""
    cls = ["street"] * n
    inner = list(range(1, n - 1))
    for i in g.sample(inner, g.choice((1, 1, 2))):
        cls[i] = "arterial"
    free = [i for i in inner if cls[i] == "street" and i not in (core0, core0 + 3)]
    for i in g.sample(free, min(len(free), g.choice((0, 1, 1, 2)))):
        cls[i] = "oneway"
    return cls


def draw_layout(draw) -> Layout:
    """Another Downtown from a draw (see the module docstring)."""
    g = keyed(draw, "layout")
    for _ in range(100000):
        nc, nr = g.choice((7, 8, 9)), g.choice((7, 8, 9))
        xs, zs = drawn_lines(g, nc, XS), drawn_lines(g, nr, ZS)
        if xs is None or zs is None:
            continue
        c0, r0 = g.randint(1, nc - 5), g.randint(1, nr - 5)
        lap = 2.0 * (xs[c0 + 3] - xs[c0] + zs[r0 + 3] - zs[r0])
        if not DRAWN_LAP_M[0] <= lap <= DRAWN_LAP_M[1]:
            continue
        col, row = drawn_classes(g, nc, c0), drawn_classes(g, nr, r0)
        if "oneway" in col + row:
            break
    else:
        raise SystemExit("gen_plan: no layout found for this draw")
    core = [(bc, br) for br in range(r0, r0 + 3) for bc in range(c0, c0 + 3)]
    plaza = g.choice(core)
    others = [b for b in core if b != plaza]
    turf = g.choice(others)
    race_block, heist_block = g.sample(others, 2)
    turns = (0.0, 90.0, 180.0, 270.0)
    return Layout(
        xs=xs,
        zs=zs,
        col_class=col,
        row_class=row,
        col_width=[g.choice(DRAWN_WIDTH[c]) for c in col],
        row_width=[g.choice(DRAWN_WIDTH[c]) for c in row],
        col_speed=[g.choice(DRAWN_SPEED[c]) for c in col],
        row_speed=[g.choice(DRAWN_SPEED[c]) for c in row],
        col_flip=[c == "oneway" and g.random() < 0.5 for c in col],
        row_flip=[c == "oneway" and g.random() < 0.5 for c in row],
        core_c=range(c0, c0 + 4),
        core_r=range(r0, r0 + 4),
        east_from=(nc - 1, g.choice([r for r in range(nr) if row[r] == "arterial"])),
        north_from=(g.choice([c for c in range(nc) if col[c] == "arterial"]), 0),
        east_len=halves(g.uniform(55.0, 85.0)),
        north_straight=halves(g.uniform(14.0, 20.0)),
        north_radius=halves(g.uniform(50.0, 70.0)),
        north_turn_deg=g.choice((-1.0, 1.0)) * halves(g.uniform(24.0, 38.0)),
        margin=halves(g.uniform(32.0, 48.0)),
        plaza_block=plaza,
        plaza_heading=g.choice(turns),
        delivery_offset=(
            g.choice((-1.0, 1.0)) * round(g.uniform(7.0, 13.0), 2),
            g.choice((-1.0, 1.0)) * round(g.uniform(5.0, 11.0), 2),
        ),
        delivery_heading=g.choice(turns),
        race_giver=(race_block, g.randrange(4), round(g.uniform(0.3, 0.7), 2)),
        heist_giver=(heist_block, g.randrange(4), round(g.uniform(0.3, 0.7), 2)),
        turf_block=turf,
        lap=(g.random() < 0.5, g.randrange(4)),
        band=(c0, r0, r0 + 3),
        drawn=True,
    )


# ------------------------------------------------------------------ roads
def north_curve(x0, z0, lay):
    """The S-curve of the north highway: straight, a turn, the same turn back, straight.
    Returns the points after the junction (the last one is the portal) as [x, 0, z]."""
    pts = [[x0, 0.0, z0 - lay.north_straight]]
    x, z, h = x0, z0 - lay.north_straight, 0.0  # heading north
    steps = 7
    for turn in (lay.north_turn_deg, -lay.north_turn_deg):
        dh = math.radians(turn) / steps
        chord = 2.0 * lay.north_radius * math.sin(abs(dh) / 2.0)
        for _ in range(steps):
            mid = h + dh / 2.0
            x += chord * math.sin(mid)
            z -= chord * math.cos(mid)
            h += dh
            pts.append([r3(x), 0.0, r3(z)])
    pts.append([r3(x), 0.0, r3(z - lay.north_straight)])
    return pts


def build_network(lay):
    nodes, edges = [], []
    for r, z in enumerate(lay.zs):
        for c, x in enumerate(lay.xs):
            nodes.append({"id": nid(c, r), "p": [x, 0.0, z], "kind": "junction"})

    def add_edge(a, b, cls, width, speed, eid=None, points=()):
        spec = ROAD[cls]
        eid = eid or f"e_{a[2:]}_{b[2:]}"
        dirs = ["ab"] if spec["oneway"] else ["ab", "ba"]
        lanes = [
            {"id": f"{eid}:{d}{k}", "dir": d, "index": k}
            for d in dirs
            for k in range(spec["lanes"])
        ]
        edges.append(
            {
                "id": eid,
                "a": a,
                "b": b,
                "class": CLASS_NAME[cls],
                "oneway": spec["oneway"],
                "lane_width_m": width,
                "speed_kmh": speed,
                "surface": "asphalt",
                "structure": "ground",
                "points": [list(p) for p in points],
                "lanes": lanes,
                "_cls": cls,
                "_half": half_of(cls, width),
            }
        )

    for c in range(len(lay.xs)):
        for r in range(len(lay.zs) - 1):
            a, b = nid(c, r), nid(c, r + 1)
            if lay.col_flip[c]:
                a, b = b, a
            add_edge(a, b, lay.col_class[c], lay.col_width[c], lay.col_speed[c])
    for r in range(len(lay.zs)):
        for c in range(len(lay.xs) - 1):
            a, b = nid(c, r), nid(c + 1, r)
            if lay.row_flip[r]:
                a, b = b, a
            add_edge(a, b, lay.row_class[r], lay.row_width[r], lay.row_speed[r])
    # The highways to the portal nodes on the map's edge.
    hw = ROAD["highway"]
    ec, er = lay.east_from
    east = {
        "id": "pt_east",
        "p": [lay.xs[ec] + lay.east_len, 0.0, lay.zs[er]],
        "kind": "portal",
    }
    nc, nr = lay.north_from
    curve = north_curve(lay.xs[nc], lay.zs[nr], lay)
    north = {"id": "pt_north", "p": curve[-1], "kind": "portal"}
    nodes += [east, north]
    add_edge(nid(ec, er), "pt_east", "highway", hw["width"], hw["speed"], "e_hw_east")
    add_edge(
        nid(nc, nr),
        "pt_north",
        "highway",
        hw["width"],
        hw["speed"],
        "e_hw_north",
        curve[:-1],
    )
    return nodes, edges


def away_dir(e, node_id, pos):
    """Unit direction of an edge leaving a node (towards its first point or other node)."""
    p = pos[node_id]
    if e["points"]:
        q = e["points"][0] if e["a"] == node_id else e["points"][-1]
    else:
        q = pos[e["b"] if e["a"] == node_id else e["a"]]
    dx, dz = q[0] - p[0], q[2] - p[2]
    length = math.hypot(dx, dz)
    return dx / length, dz / length


def drawn_timing(seed, node_id):
    """A drawn layout's signal draws for one junction: whether a junction of streets gets
    signals, then (in leg order) the greens, the walk, amber and all-red times, the offset."""
    g = keyed(seed, "signal", node_id)
    return {"signal": g.random() < DRAWN_SIGNAL_SHARE, "rng": g}


def build_intersections(nodes, edges, lay, rng, seed):
    pos = {n["id"]: n["p"] for n in nodes}
    incident = {n["id"]: [] for n in nodes}
    for e in edges:
        incident[e["a"]].append(e)
        incident[e["b"]].append(e)
    grid = {nid(c, r): (c, r) for r in range(len(lay.zs)) for c in range(len(lay.xs))}
    out = []
    for n in nodes:
        nid_ = n["id"]
        inc = incident[nid_]
        has_arterial = any(RANK[e["_cls"]] >= 2 for e in inc)
        timing = drawn_timing(seed, nid_) if lay.drawn else None
        if n["kind"] == "portal":
            control = "none"
        elif len(inc) <= 2:
            control = "none"
            n["kind"] = "bend" if len(inc) == 2 else "end"
        elif has_arterial or (timing and len(inc) == 4 and timing["signal"]):
            control = "signal"
        else:
            control = "stop"

        def away(e, nid_=nid_):
            return away_dir(e, nid_, pos)

        legs = []
        for e in sorted(inc, key=lambda e: heading_of(*away(e))):
            dx, dz = away(e)
            cross = [
                o["_half"]
                for o in inc
                if o is not e and abs(dx * away(o)[0] + dz * away(o)[1]) < 1e-6
            ]
            box = max(cross) if cross else 0.0
            entering = "ab" if e["b"] == nid_ else "ba"
            has_lanes_in = any(ln["dir"] == entering for ln in e["lanes"])
            if control == "none":
                crosswalk = None
                stop = box
            else:
                crosswalk = {
                    "id": f"cw_{nid_}_{e['id']}",
                    "from_m": box + CROSSWALK_GAP_M,
                    "to_m": box + CROSSWALK_GAP_M + CROSSWALK_W,
                }
                stop = crosswalk["to_m"] + STOP_GAP_M
            approach = None
            if has_lanes_in:
                approach = {
                    "id": f"{nid_}<{e['id']}",
                    "dir": entering,
                    "stop_line_m": stop,
                }
            legs.append(
                {
                    "edge": e["id"],
                    "box_m": box,
                    "crosswalk": crosswalk,
                    "approach": approach,
                }
            )
        rec = {"id": nid_, "node": nid_, "control": control, "legs": legs}
        if control == "signal":
            draw = timing["rng"] if timing else None
            phases = []
            for leg in legs:
                if leg["approach"] is None:
                    continue
                cls = next(e["_cls"] for e in inc if e["id"] == leg["edge"])
                if draw is None:
                    green = 12.0 if RANK[cls] >= 2 else 9.0
                elif RANK[cls] >= 2:
                    green = halves(draw.uniform(11.0, 15.0))
                else:
                    green = halves(draw.uniform(8.0, 11.0))
                phases.append(
                    {
                        "green": [leg["approach"]["id"]],
                        "walk": [],
                        "green_s": green,
                    }
                )
            walk = [leg["crosswalk"]["id"] for leg in legs if leg["crosswalk"]]
            if draw is None:
                walk_s, amber, all_red = 7.0, 3.0, 1.0
            else:
                walk_s = halves(draw.uniform(6.0, 9.0))
                amber = draw.choice((3.0, 3.5, 4.0))
                all_red = draw.choice((1.0, 1.5, 2.0))
            phases.append({"green": [], "walk": walk, "green_s": walk_s})
            cycle = sum(ph["green_s"] + amber + all_red for ph in phases)
            if draw is None:
                c, r = grid.get(nid_, (None, None))
                core = c is not None and is_core_node(lay, c, r)
                draw = rng if core else keyed(seed, nid_)
            rec["signal"] = {
                "phases": phases,
                "amber_s": amber,
                "all_red_s": all_red,
                "offset_s": round(draw.uniform(0.0, cycle), 1),
            }
        out.append(rec)
    return out


# ------------------------------------------------------------------ blocks and parcels
def rect(x0, z0, x1, z1):
    return [[x0, z0], [x1, z0], [x1, z1], [x0, z1]]


def block_rect(lay, bc, br):
    x0 = lay.xs[bc] + lay.col_half(bc)
    x1 = lay.xs[bc + 1] - lay.col_half(bc + 1)
    z0 = lay.zs[br] + lay.row_half(br)
    z1 = lay.zs[br + 1] - lay.row_half(br + 1)
    return x0, z0, x1, z1


def facing_side(lay, bc, br, quad):
    """The parcel side (N, S, E, W) that faces the busier of its two outer roads."""
    ns = "N" if quad[0] == "N" else "S"
    ew = "W" if quad[1] == "W" else "E"
    row = br if ns == "N" else br + 1
    col = bc if ew == "W" else bc + 1
    if RANK[lay.col_class[col]] > RANK[lay.row_class[row]]:
        return ew
    return ns


def side_rank(lay, bc, br, side):
    """The rank of the road beyond one side of block (bc, br)."""
    return {
        "N": RANK[lay.row_class[br]],
        "S": RANK[lay.row_class[br + 1]],
        "W": RANK[lay.col_class[bc]],
        "E": RANK[lay.col_class[bc + 1]],
    }[side]


INWARD = {"N": 180.0, "S": 0.0, "W": 90.0, "E": 270.0}


def side_mid(fx0, fz0, fx1, fz1, side):
    return {
        "N": ((fx0 + fx1) / 2.0, fz0),
        "S": ((fx0 + fx1) / 2.0, fz1),
        "W": (fx0, (fz0 + fz1) / 2.0),
        "E": (fx1, (fz0 + fz1) / 2.0),
    }[side]


def inward_vec(side):
    return {"N": (0.0, 1.0), "S": (0.0, -1.0), "W": (1.0, 0.0), "E": (-1.0, 0.0)}[side]


def room_rect(door, side, depth, width, foot):
    """A room behind the door, depth into the building, width across, inside the walls."""
    fx0, fz0, fx1, fz1 = foot
    ix, iz = inward_vec(side)
    dx, dz = door
    if ix == 0.0:
        x0, x1 = dx - width / 2.0, dx + width / 2.0
        z0, z1 = sorted([dz, dz + iz * depth])
    else:
        z0, z1 = dz - width / 2.0, dz + width / 2.0
        x0, x1 = sorted([dx, dx + ix * depth])
    wall = 0.3
    x0, x1 = max(x0, fx0 + wall), min(x1, fx1 - wall)
    z0, z1 = max(z0, fz0 + wall), min(z1, fz1 - wall)
    return [round(x0, 2), round(z0, 2), round(x1, 2), round(z1, 2)]


def r2(v):
    return [round(a, 3) for a in v]


def outer_area(lay, bc, br):
    """The layout family of an outer block: east of the core it is commercial and
    industrial (towards the port); north, west and south it is residential."""
    return "east" if bc > max(lay.core_bc) and min(lay.core_br) <= br else "residential"


def block_zoning(lay, bc, br, seed):
    if bc in lay.core_bc and br in lay.core_br:
        return CORE_ZONING[(bc - min(lay.core_bc), br - min(lay.core_br))]
    return keyed(seed, "zoning", bc, br).choice(OUTER_ZONING[outer_area(lay, bc, br)])


def build_blocks(lay, rng, seed):
    """Blocks, sidewalks and parcels. Core blocks first (core parcels are p_00 to p_32 and
    draw from the core's generator), then the rest."""
    core = [(bc, br) for br in lay.core_br for bc in lay.core_bc]
    rest = [
        (bc, br)
        for br in range(len(lay.zs) - 1)
        for bc in range(len(lay.xs) - 1)
        if (bc, br) not in core
    ]
    blocks, sidewalks, parcels, placed = [], [], [], []
    pid = 0
    for bc, br in core + rest:
        bid = f"b_{bc}{br}"
        draw = rng if (bc, br) in core else keyed(seed, bid)
        x0, z0, x1, z1 = block_rect(lay, bc, br)
        blocks.append({"id": bid, "poly": rect(x0, z0, x1, z1), "elevation_m": CURB_M})
        o = SIDEWALK_W / 2.0
        sidewalks.append(
            {
                "id": f"sw_{bc}{br}",
                "block": bid,
                "width_m": SIDEWALK_W,
                "elevation_m": CURB_M,
                "ring": rect(x0 + o, z0 + o, x1 - o, z1 - o),
            }
        )
        ix0, iz0 = x0 + SIDEWALK_W, z0 + SIDEWALK_W
        ix1, iz1 = x1 - SIDEWALK_W, z1 - SIDEWALK_W
        zones = block_zoning(lay, bc, br, seed)
        if len(zones) == 1:
            cells = [("ALL", (ix0, iz0, ix1, iz1))]
        else:
            mx = round(ix0 + (ix1 - ix0) * draw.uniform(0.4, 0.6), 2)
            mz = round(iz0 + (iz1 - iz0) * draw.uniform(0.4, 0.6), 2)
            cells = [
                ("NW", (ix0, iz0, mx, mz)),
                ("NE", (mx, iz0, ix1, mz)),
                ("SW", (ix0, mz, mx, iz1)),
                ("SE", (mx, mz, ix1, iz1)),
            ]
        for (quad, (px0, pz0, px1, pz1)), zone in zip(cells, zones, strict=True):
            lo, hi = ZONING[zone]
            height = round(draw.uniform(lo, hi), 1) if zone in BUILT else 0.0
            parcel = {
                "id": f"p_{pid:02d}",
                "block": bid,
                "zoning": zone,
                "poly": rect(px0, pz0, px1, pz1),
                "base_m": CURB_M,
                "height_m": height,
                "height_range_m": [lo, hi],
                "setback_m": SETBACK_M if zone in BUILT else 0.0,
                "interior": None,
            }
            parcels.append(parcel)
            placed.append((bid, bc, br, quad, parcel))
            pid += 1
    return blocks, sidewalks, parcels, placed


def split_cells(g, pattern, ix0, iz0, ix1, iz1):
    """The parcels of a drawn block, north row first, west to east: the whole block, two
    halves across its longer side, quarters, or sixths (three along the longer side)."""
    w, h = ix1 - ix0, iz1 - iz0

    def cut(v0, size, lo, hi):
        return round(v0 + size * g.uniform(lo, hi), 2)

    if pattern == "whole":
        xs, zs = [ix0, ix1], [iz0, iz1]
    elif pattern == "halves" and w >= h:
        xs, zs = [ix0, cut(ix0, w, 0.38, 0.62), ix1], [iz0, iz1]
    elif pattern == "halves":
        xs, zs = [ix0, ix1], [iz0, cut(iz0, h, 0.38, 0.62), iz1]
    elif pattern == "quads":
        xs = [ix0, cut(ix0, w, 0.38, 0.62), ix1]
        zs = [iz0, cut(iz0, h, 0.38, 0.62), iz1]
    elif w >= h:
        xs = [ix0, cut(ix0, w, 0.28, 0.38), cut(ix0, w, 0.62, 0.72), ix1]
        zs = [iz0, cut(iz0, h, 0.4, 0.6), iz1]
    else:
        xs = [ix0, cut(ix0, w, 0.4, 0.6), ix1]
        zs = [iz0, cut(iz0, h, 0.28, 0.38), cut(iz0, h, 0.62, 0.72), iz1]
    return [
        (xs[i], zs[j], xs[i + 1], zs[j + 1])
        for j in range(len(zs) - 1)
        for i in range(len(xs) - 1)
    ]


def build_blocks_drawn(lay, seed):
    """A drawn layout's blocks and sidewalks, and its parcels as outlines whose zonings are
    drawn once the points of interest have their parcels (blocks row by row)."""
    core = {(bc, br) for br in lay.core_br for bc in lay.core_bc}
    blocks, sidewalks, stubs = [], [], []
    for br in range(len(lay.zs) - 1):
        for bc in range(len(lay.xs) - 1):
            bid = f"b_{bc}{br}"
            g = keyed(seed, bid)
            x0, z0, x1, z1 = block_rect(lay, bc, br)
            width = g.choice((2.5, 3.0, 3.5))
            blocks.append(
                {"id": bid, "poly": rect(x0, z0, x1, z1), "elevation_m": CURB_M}
            )
            o = width / 2.0
            sidewalks.append(
                {
                    "id": f"sw_{bc}{br}",
                    "block": bid,
                    "width_m": width,
                    "elevation_m": CURB_M,
                    "ring": rect(x0 + o, z0 + o, x1 - o, z1 - o),
                }
            )
            inner = (x0 + width, z0 + width, x1 - width, z1 - width)
            area = "core" if (bc, br) in core else outer_area(lay, bc, br)
            whole = None
            if (bc, br) == lay.plaza_block:
                pattern, whole = "whole", "plaza"
            else:
                pattern = pick(g, DRAWN_SPLITS[area])
                if pattern == "whole":
                    whole = g.choice(DRAWN_WHOLE[area])
            for cell in split_cells(g, pattern, *inner):
                sides = [
                    s
                    for s, on in zip(
                        SIDES,
                        (
                            cell[1] == inner[1],
                            cell[2] == inner[2],
                            cell[3] == inner[3],
                            cell[0] == inner[0],
                        ),
                        strict=True,
                    )
                    if on
                ]
                stubs.append(
                    {
                        "id": f"p_{len(stubs):02d}",
                        "block": bid,
                        "bc": bc,
                        "br": br,
                        "area": area,
                        "rect": cell,
                        "sides": sides,
                        "sidewalk_m": width,
                        "setback": g.choice((2.5, 3.0, 3.5)),
                        "zoning": whole,
                    }
                )
    return blocks, sidewalks, stubs


def drawn_room(spec, g):
    """A drawn layout's door and rooms for one point of interest on a building (None for
    the open ones): sizes, the door's place along its side, its width and height."""
    kind = spec["kind"]
    if kind not in ("shop", "safehouse", "bank", "hospital", "police_station"):
        return None
    room = {"door_at": round(g.uniform(0.3, 0.7), 3)}
    if kind in ("hospital", "police_station"):
        return room
    if kind == "safehouse":
        room["depth"], room["width"] = (
            round(g.uniform(7.0, 9.0), 1),
            round(g.uniform(7.0, 9.5), 1),
        )
    elif kind == "shop":
        room["depth"], room["width"] = (
            round(g.uniform(8.5, 12.0), 1),
            round(g.uniform(10.0, 13.5), 1),
        )
    else:
        room["depth"], room["width"] = (
            round(g.uniform(9.0, 11.5), 1),
            round(g.uniform(10.0, 13.0), 1),
        )
        room["vault"] = (
            round(g.uniform(5.0, 7.0), 1),
            round(g.uniform(6.5, 9.0), 1),
            round(g.uniform(2.8, 3.2), 2),
        )
    room["ceiling"] = round(g.uniform(3.2, 4.0), 2)
    room["door_w"] = g.choice((1.8, 2.0, 2.2, 2.4))
    room["door_h"] = g.choice((2.4, 2.6, 2.8))
    return room


def footprint(stub):
    px0, pz0, px1, pz1 = stub["rect"]
    sb = stub["setback"]
    return (px0 + sb, pz0 + sb, px1 - sb, pz1 - sb)


def along_and_deep(box, side):
    """A rectangle's length along one side and its depth behind it."""
    x0, z0, x1, z1 = box
    return (x1 - x0, z1 - z0) if side in ("N", "S") else (z1 - z0, x1 - x0)


def fits(stub, spec, room, side):
    """Whether a point of interest (with its drawn rooms) fits on a parcel facing side."""
    kind = spec["kind"]
    if kind in ("garage", "mission_point"):
        along, deep = along_and_deep(stub["rect"], side)
        return along >= 12.0 and deep >= (10.0 if kind == "garage" else 12.0)
    along, deep = along_and_deep(footprint(stub), side)
    if kind in ("hospital", "police_station"):
        return along >= 10.0 and deep >= 10.0
    width, depth = room["width"], room["depth"]
    if "vault" in room:
        width, depth = max(width, room["vault"][1]), depth + room["vault"][0]
    return along >= width + 1.6 and deep >= depth + 0.8


def assign_pois(stubs, lay, seed, rooms):
    """Parcels of the core (and the side each faces) for the points of interest: drawn,
    each on its own parcel facing the busiest road that leaves it room, the pairs of APART
    in different blocks."""
    g = keyed(seed, "pois")
    core = [s for s in stubs if s["area"] == "core" and s["zoning"] is None]
    for _ in range(1000):
        order = core[:]
        g.shuffle(order)
        got, used = {}, set()
        for pid in DRAWN_ORDER:
            spec, hit = SPECS[pid], None
            for s in order:
                partner = got.get(APART.get(pid))
                if s["id"] in used or (partner and partner[0]["block"] == s["block"]):
                    continue
                ties = {side: g.random() for side in s["sides"]}
                ranked = sorted(
                    s["sides"],
                    key=lambda d, s=s: (-side_rank(lay, s["bc"], s["br"], d), ties[d]),
                )
                side = next(
                    (d for d in ranked if fits(s, spec, rooms[pid], d)),
                    None,
                )
                if side is not None:
                    hit = (s, side)
                    break
            if hit is None:
                break
            got[pid] = hit
            used.add(hit[0]["id"])
        else:
            return got
    raise SystemExit("gen_plan: the core has no room for the points of interest")


def finish_parcels(stubs, got, seed):
    """Every parcel of a drawn layout, its zoning drawn unless a point of interest or the
    block fixes it."""
    forced = {s["id"]: POI_ZONING[SPECS[pid]["kind"]] for pid, (s, _) in got.items()}
    parcels = []
    for s in stubs:
        g = keyed(seed, "parcel", s["id"])
        zone = forced.get(s["id"]) or s["zoning"] or pick(g, DRAWN_ZONES[s["area"]])
        lo, hi = ZONING[zone]
        parcels.append(
            {
                "id": s["id"],
                "block": s["block"],
                "zoning": zone,
                "poly": rect(*s["rect"]),
                "base_m": CURB_M,
                "height_m": round(g.uniform(lo, hi), 1) if zone in BUILT else 0.0,
                "height_range_m": [lo, hi],
                "setback_m": s["setback"] if zone in BUILT else 0.0,
                "interior": None,
            }
        )
    return parcels


def door_on(foot, side, room):
    """The door's point on the footprint side, at the drawn fraction of the side, moved so
    the widest room behind it stays inside the walls."""
    fx0, fz0, fx1, fz1 = foot
    width = 0.0
    if room and "width" in room:
        width = max(room["width"], room.get("vault", (0.0, 0.0))[1])
    lo, hi = (fx0, fx1) if side in ("N", "S") else (fz0, fz1)
    reach = width / 2.0 + 0.3 if width else 2.0
    t = min(max(lo + (hi - lo) * room["door_at"], lo + reach), hi - reach)
    if side in ("N", "S"):
        return (round(t, 2), fz0 if side == "N" else fz1)
    return (fx0 if side == "W" else fx1, round(t, 2))


def place_pois_drawn(parcels, got, rooms, geo):
    """A drawn layout's points of interest on parcels, with their doors and interiors."""
    by_id = {p["id"]: p for p in parcels}
    pois = []
    for pid, (stub, side) in sorted(got.items(), key=lambda kv: kv[1][0]["id"]):
        spec, room = SPECS[pid], rooms[pid]
        kind = spec["kind"]
        parcel = by_id[stub["id"]]
        px0, pz0, px1, pz1 = stub["rect"]
        ix, iz = inward_vec(side)
        out_m = stub["sidewalk_m"] + 1.2  # past the sidewalk, into the near lane
        poi = {"id": pid, "kind": kind}
        if kind == "mission_point":
            poi["p"] = [
                round((px0 + px1) / 2.0, 2),
                CURB_M,
                round((pz0 + pz1) / 2.0, 2),
            ]
            poi["heading_deg"] = INWARD[side]
            poi["radius_m"] = 6.0
            pois.append(poi)
            continue
        if kind == "garage":
            sx, sz = side_mid(px0, pz0, px1, pz1, side)
            zx, zz = sx + ix * 4.0, sz + iz * 4.0
            half_w, half_d = 4.5, 3.5
            if ix == 0.0:
                zone = rect(zx - half_w, zz - half_d, zx + half_w, zz + half_d)
            else:
                zone = rect(zx - half_d, zz - half_w, zx + half_d, zz + half_w)
            lane, s = nearest_lane(geo, sx - ix * out_m, sz - iz * out_m)
            poi["p"] = [round(zx, 2), CURB_M, round(zz, 2)]
            poi["heading_deg"] = INWARD[side]
            poi["zone"] = {"poly": [r2(v) for v in zone], "heading_deg": INWARD[side]}
            poi["driveway"] = {"lane": lane, "s": s}
            poi["capacity"] = 2
            pois.append(poi)
            continue
        foot = footprint(stub)
        door = door_on(foot, side, room)
        outside = [
            round(door[0] - ix * 1.5, 2),
            CURB_M,
            round(door[1] - iz * 1.5, 2),
        ]
        poi["parcel"] = parcel["id"]
        if kind in ("hospital", "police_station"):
            back = stub["setback"] + out_m
            lane, s = nearest_lane(geo, door[0] - ix * back, door[1] - iz * back)
            poi["p"] = outside
            poi["heading_deg"] = INWARD[side]
            poi["exit"] = {"lane": lane, "s": s}
            poi["respawn"] = outside
            pois.append(poi)
            continue
        depth = room["depth"]
        rooms_ = [
            {
                "id": "main",
                "poly": rect(*room_rect(door, side, depth, room["width"], foot)),
                "floor_m": CURB_M,
                "ceiling_m": round(CURB_M + room["ceiling"], 2),
            }
        ]
        if kind == "bank":
            vd, vw, vc = room["vault"]
            vault_door = (door[0] + ix * depth, door[1] + iz * depth)
            rooms_.append(
                {
                    "id": "vault",
                    "poly": rect(*room_rect(vault_door, side, vd, vw, foot)),
                    "floor_m": CURB_M,
                    "ceiling_m": round(CURB_M + vc, 2),
                }
            )
        inside = [
            round(door[0] + ix * (depth - 3.0), 2),
            CURB_M,
            round(door[1] + iz * (depth - 3.0), 2),
        ]
        points = {}
        if kind == "shop":
            points["counter"] = inside
        elif kind == "safehouse":
            points["save"] = inside
        parcel["interior"] = {
            "door": {
                "p": [door[0], door[1]],
                "heading_deg": INWARD[side],
                "width_m": room["door_w"],
                "height_m": room["door_h"],
            },
            "rooms": rooms_,
            "points": points,
        }
        if kind == "shop":
            poi.update(shop=spec["shop"], point="counter", p=inside)
        elif kind == "safehouse":
            poi.update(point="save", p=inside)
        else:
            poi.update(vault="vault", p=outside)
        poi["heading_deg"] = INWARD[side]
        pois.append(poi)
    return pois


# ------------------------------------------------------------------ points of interest
def lane_geometry(edges, nodes, intersections):
    """Start, direction and length of every lane of a straight edge (FORMAT.md)."""
    pos = {n["id"]: n["p"] for n in nodes}
    legs = {}
    for it in intersections:
        for leg in it["legs"]:
            legs[(it["node"], leg["edge"])] = leg
    out = {}
    for e in edges:
        if e["points"]:
            continue
        pa, pb = pos[e["a"]], pos[e["b"]]
        n = sum(1 for ln in e["lanes"])
        for ln in e["lanes"]:
            start, end = (e["a"], e["b"]) if ln["dir"] == "ab" else (e["b"], e["a"])
            ps, pe = (pa, pb) if ln["dir"] == "ab" else (pb, pa)
            dx, dz = pe[0] - ps[0], pe[2] - ps[2]
            length = math.hypot(dx, dz)
            ux, uz = dx / length, dz / length
            rx, rz = -uz, ux
            w = e["lane_width_m"]
            if e["oneway"]:
                off = (ln["index"] + 0.5 - n / 2.0) * w
            else:
                off = (ln["index"] + 0.5) * w
            s0 = legs[(start, e["id"])]["box_m"]
            s1 = legs[(end, e["id"])]["approach"]["stop_line_m"]
            origin = (ps[0] + ux * s0 + rx * off, ps[2] + uz * s0 + rz * off)
            out[ln["id"]] = {
                "origin": origin,
                "dir": (ux, uz),
                "length": length - s0 - s1,
                "y": ps[1],
                "class": e["class"],
            }
    return out


def lane_point(geo, lane_id, s):
    g = geo[lane_id]
    x = g["origin"][0] + g["dir"][0] * s
    z = g["origin"][1] + g["dir"][1] * s
    return [round(x, 3), g["y"], round(z, 3)], heading_of(*g["dir"])


def nearest_lane(geo, x, z):
    best = None
    for lid, g in geo.items():
        if g["class"] == "highway":
            continue
        ox, oz = g["origin"]
        ux, uz = g["dir"]
        s = (x - ox) * ux + (z - oz) * uz
        s = min(max(s, 1.0), g["length"] - 1.0)
        px, pz = ox + ux * s, oz + uz * s
        d = math.hypot(x - px, z - pz)
        if best is None or d < best[0]:
            best = (d, lid, round(s, 2))
    return best[1], best[2]


def place_pois(placed, geo, lay):
    pois = []
    lo_c, lo_r = min(lay.core_bc), min(lay.core_br)
    for _bid, bc, br, quad, parcel in placed:
        spec = PARCEL_POIS.get(((bc - lo_c, br - lo_r), quad))
        if spec is None or bc not in lay.core_bc or br not in lay.core_br:
            continue
        (px0, pz0), _, (px1, pz1), _ = parcel["poly"]
        centre = ((px0 + px1) / 2.0, (pz0 + pz1) / 2.0)
        side = facing_side(lay, bc, br, quad)
        ix, iz = inward_vec(side)
        kind = spec["kind"]
        poi = {"id": spec["id"], "kind": kind}
        if kind in ("mission_point",):
            poi["p"] = [round(centre[0], 2), CURB_M, round(centre[1], 2)]
            poi["heading_deg"] = INWARD[side]
            poi["radius_m"] = 6.0
            pois.append(poi)
            continue
        if kind == "garage":
            sx, sz = side_mid(px0, pz0, px1, pz1, side)
            zx, zz = sx + ix * 4.0, sz + iz * 4.0
            half_w, half_d = 4.5, 3.5
            if ix == 0.0:
                zone = rect(zx - half_w, zz - half_d, zx + half_w, zz + half_d)
            else:
                zone = rect(zx - half_d, zz - half_w, zx + half_d, zz + half_w)
            lane, s = nearest_lane(geo, sx - ix * 6.0, sz - iz * 6.0)
            poi["p"] = [round(zx, 2), CURB_M, round(zz, 2)]
            poi["heading_deg"] = INWARD[side]
            poi["zone"] = {"poly": [r2(v) for v in zone], "heading_deg": INWARD[side]}
            poi["driveway"] = {"lane": lane, "s": s}
            poi["capacity"] = 2
            pois.append(poi)
            continue
        foot = (px0 + SETBACK_M, pz0 + SETBACK_M, px1 - SETBACK_M, pz1 - SETBACK_M)
        door = side_mid(*foot, side)
        depth, width = spec.get("room", (10.0, 12.0))
        rooms = [
            {
                "id": "main",
                "poly": rect(*room_rect(door, side, depth, width, foot)),
                "floor_m": CURB_M,
                "ceiling_m": CURB_M + 3.6,
            }
        ]
        points = {}
        inside = (door[0] + ix * (depth - 3.0), door[1] + iz * (depth - 3.0))
        if kind == "bank":
            vault_door = (door[0] + ix * depth, door[1] + iz * depth)
            vault = room_rect(vault_door, side, 6.0, 8.0, foot)
            rooms.append(
                {
                    "id": "vault",
                    "poly": rect(*vault),
                    "floor_m": CURB_M,
                    "ceiling_m": CURB_M + 3.0,
                }
            )
        if kind == "shop":
            points["counter"] = [round(inside[0], 2), CURB_M, round(inside[1], 2)]
        if kind == "safehouse":
            points["save"] = [round(inside[0], 2), CURB_M, round(inside[1], 2)]
        # Only shops, safehouses and the bank have interiors (GDD scope); the police
        # station and the hospital keep a front door point outside the facade.
        if kind in ("shop", "safehouse", "bank"):
            parcel["interior"] = {
                "door": {
                    "p": [round(door[0], 2), round(door[1], 2)],
                    "heading_deg": INWARD[side],
                    "width_m": 2.0,
                    "height_m": 2.6,
                },
                "rooms": rooms,
                "points": points,
            }
        outside = [
            round(door[0] - ix * 1.5, 2),
            CURB_M,
            round(door[1] - iz * 1.5, 2),
        ]
        poi["parcel"] = parcel["id"]
        if kind == "shop":
            poi["shop"] = spec["shop"]
            poi["point"] = "counter"
            poi["p"] = points["counter"]
            poi["heading_deg"] = INWARD[side]
        elif kind == "safehouse":
            poi["point"] = "save"
            poi["p"] = points["save"]
            poi["heading_deg"] = INWARD[side]
        elif kind == "bank":
            poi["vault"] = "vault"
            poi["p"] = outside
            poi["heading_deg"] = INWARD[side]
        else:
            lane, s = nearest_lane(geo, door[0] - ix * 9.0, door[1] - iz * 9.0)
            poi["p"] = outside
            poi["heading_deg"] = INWARD[side]
            poi["exit"] = {"lane": lane, "s": s}
            poi["respawn"] = outside
        pois.append(poi)
    return pois


def race_pois(geo, edges, lay):
    """R1: two laps round the core's perimeter (clockwise from its north side in the
    default layout): the start on the middle edge of the first side, a checkpoint on each
    end edge of every side, the first side's last edge first and its first edge last."""
    by_ends = {frozenset((e["a"], e["b"])): e for e in edges}
    c0, c1 = lay.core_c[0], lay.core_c[-1]
    r0, r1 = lay.core_r[0], lay.core_r[-1]
    loop = [  # node runs, clockwise: north, east, south, west
        [nid(c, r0) for c in range(c0, c1 + 1)],
        [nid(c1, r) for r in range(r0, r1 + 1)],
        [nid(c, r1) for c in range(c1, c0 - 1, -1)],
        [nid(c0, r) for r in range(r1, r0 - 1, -1)],
    ]
    clockwise, start = lay.lap
    if not clockwise:
        loop = [run[::-1] for run in loop[::-1]]
        start = 3 - start
    loop = loop[start:] + loop[:start]
    sides = []
    for run in loop:
        legs = []
        for u, v in itertools.pairwise(run):
            e = by_ends[frozenset((u, v))]
            legs.append((e["id"], "ab" if e["a"] == u else "ba"))
        sides.append(legs)
    route = [sides[0][-1]]
    for legs in sides[1:]:
        route += [legs[0], legs[-1]]
    route.append(sides[0][0])
    pois = []
    eid, d = sides[0][len(sides[0]) // 2]
    lane = f"{eid}:{d}0"
    p, h = lane_point(geo, lane, geo[lane]["length"] / 2.0)
    pois.append(
        {
            "id": "r1_start",
            "kind": "mission_point",
            "p": p,
            "heading_deg": h,
            "radius_m": 12.0,
        }
    )
    for i, (eid, d) in enumerate(route, start=1):
        lane = f"{eid}:{d}0"
        p, h = lane_point(geo, lane, geo[lane]["length"] / 2.0)
        pois.append(
            {
                "id": f"r1_cp{i}",
                "kind": "checkpoint",
                "race": "R1",
                "index": i,
                "p": p,
                "heading_deg": h,
                "radius_m": 12.0,
            }
        )
    return pois


def ring_point(sidewalk, frac_side, side_index):
    ring = sidewalk["ring"]
    a, b = ring[side_index], ring[(side_index + 1) % len(ring)]
    x = a[0] + (b[0] - a[0]) * frac_side
    z = a[1] + (b[1] - a[1]) * frac_side
    return [round(x, 2), CURB_M, round(z, 2)]


# Outward headings of the sides of a sidewalk ring (north, east, south, west in ring order).
RING_OUT = (0.0, 90.0, 180.0, 270.0)


def people_pois(sidewalks, parcels, lay):
    sw = {s["id"]: s for s in sidewalks}
    pc, pr = lay.plaza_block
    plaza = next(p for p in parcels if p["block"] == f"b_{pc}{pr}")
    (px0, pz0), _, (px1, pz1), _ = plaza["poly"]
    cx, cz = (px0 + px1) / 2.0, (pz0 + pz1) / 2.0
    dx, dz = lay.delivery_offset

    def giver(spec):
        (bc, br), side, frac = spec
        return ring_point(sw[f"sw_{bc}{br}"], frac, side), RING_OUT[side]

    race_p, race_h = giver(lay.race_giver)
    heist_p, heist_h = giver(lay.heist_giver)
    return [
        {
            "id": "plaza_central",
            "kind": "plaza",
            "parcel": plaza["id"],
            "p": [round(cx, 2), CURB_M, round(cz, 2)],
            "heading_deg": lay.plaza_heading,
        },
        {
            "id": "giver_delivery",
            "kind": "mission_giver",
            "giver": "giver_delivery",
            "p": [round(cx + dx, 2), CURB_M, round(cz + dz, 2)],
            "heading_deg": lay.delivery_heading,
        },
        {
            "id": "giver_race",
            "kind": "mission_giver",
            "giver": "giver_race",
            "p": race_p,
            "heading_deg": race_h,
        },
        {
            "id": "giver_heist",
            "kind": "mission_giver",
            "giver": "giver_heist",
            "p": heist_p,
            "heading_deg": heist_h,
        },
    ]


def portal_pois(nodes, edges):
    """The two highway portals: where each highway meets the map's edge."""
    pos = {n["id"]: n["p"] for n in nodes}
    out = []
    for poi_id, node, link in (
        ("highway_downtown_port", "pt_east", "hw_downtown_port"),
        ("highway_downtown_hills", "pt_north", "hw_downtown_hills"),
    ):
        e = next(e for e in edges if e["b"] == node)
        before = e["points"][-1] if e["points"] else pos[e["a"]]
        p = pos[node]
        out.append(
            {
                "id": poi_id,
                "kind": "portal",
                "node": node,
                "link": link,
                "p": [p[0], p[1], p[2]],
                "heading_deg": heading_of(p[0] - before[0], p[2] - before[2]),
            }
        )
    return out


def districts(bounds, lay):
    """The residential north, west and south first, then the core (first match wins). The
    highway district starts past the portals, on the other maps."""
    (bx0, bz0), (bx1, bz1) = bounds["min"], bounds["max"]
    c, ra, rb = lay.band
    xs, zs = lay.xs, lay.zs
    return [
        {
            "id": "downtown_residential",
            "poly": [
                [bx0, bz0], [bx1, bz0], [bx1, zs[ra]], [xs[c], zs[ra]],
                [xs[c], zs[rb]], [bx1, zs[rb]], [bx1, bz1], [bx0, bz1],
            ],
        },
        {"id": "downtown_core", "poly": rect(bx0, bz0, bx1, bz1)},
    ]  # fmt: skip


def build_plan(lay, seed):
    """The plan of a layout (seed: the default layout's --seed, or a drawn layout's draw)."""
    rng = random.Random(seed)
    nodes, edges = build_network(lay)
    intersections = build_intersections(nodes, edges, lay, rng, seed)
    geo = lane_geometry(edges, nodes, intersections)
    if lay.drawn:
        blocks, sidewalks, stubs = build_blocks_drawn(lay, seed)
        rooms = {
            pid: drawn_room(SPECS[pid], keyed(seed, "room", pid)) for pid in DRAWN_ORDER
        }
        got = assign_pois(stubs, lay, seed, rooms)
        parcels = finish_parcels(stubs, got, seed)
        pois = place_pois_drawn(parcels, got, rooms, geo)
    else:
        blocks, sidewalks, parcels, placed = build_blocks(lay, rng, seed)
        pois = place_pois(placed, geo, lay)
    pois += race_pois(geo, edges, lay)
    pois += people_pois(sidewalks, parcels, lay)
    pois += portal_pois(nodes, edges)
    for e in edges:
        del e["_cls"], e["_half"]

    north = next(n for n in nodes if n["id"] == "pt_north")
    east = next(n for n in nodes if n["id"] == "pt_east")
    bounds = {
        "min": [lay.xs[0] - lay.margin, north["p"][2]],
        "max": [east["p"][0], lay.zs[-1] + lay.margin],
    }
    tc, tr = lay.turf_block
    return {
        "format": FORMAT,
        "map": "downtown",
        "name": "downtown",
        "revision": 2,
        "note": "Downtown: the core block and the blocks around it, with the highways to "
        "Ashby Port (east) and Sable Hills (north).",
        "bounds": bounds,
        "ground_m": 0.0,
        "nodes": nodes,
        "edges": edges,
        "intersections": intersections,
        "blocks": blocks,
        "sidewalks": sidewalks,
        "parcels": parcels,
        "water": [],
        "terrain": None,
        "districts": districts(bounds, lay),
        "turfs": [
            {
                "id": "turf_crew_a",
                "crew": "crew_a",
                "poly": rect(lay.xs[tc], lay.zs[tr], lay.xs[tc + 1], lay.zs[tr + 1]),
            }
        ],
        "pois": pois,
        "spawn": {
            "vehicle_edges": "all",
            "pedestrian_areas": [s["id"] for s in sidewalks]
            + [p["id"] for p in parcels if p["zoning"] in ("plaza", "park")],
            "no_spawn": [],
        },
    }


def drawn_problems(plan):
    """scripts/check_plan.py's problems with a drawn plan, the GDD's Downtown ids included."""
    here = Path(__file__).resolve().parent
    sys.path.insert(0, str(here))
    from check_plan import Plan, gdd_problems

    found = Plan(plan).check()
    gdd = here.parent / "common" / "design" / "GDD.md"
    if gdd.is_file():
        found += gdd_problems(gdd.read_text(), [plan])[0]
    return found


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--seed", type=int, default=11)
    ap.add_argument("--out", required=True)
    ap.add_argument("--layout", choices=("default", "random"), default="default")
    ap.add_argument("--draw", type=int, help="with --layout random: the draw")
    ap.add_argument("--draw-file", type=Path, help='or a JSON file with {"draw": N}')
    args = ap.parse_args()
    if args.layout == "random":
        if (args.draw is None) == (args.draw_file is None):
            ap.error("--layout random takes one of --draw and --draw-file")
        draw = args.draw
        if draw is None:
            draw = int(json.loads(args.draw_file.read_text())["draw"])
        plan = build_plan(draw_layout(draw), draw)
        found = drawn_problems(plan)
        if found:
            print("\n".join(found))
            print(
                f"gen_plan: the drawn plan has {len(found)} problems; nothing written"
            )
            return 1
    else:
        plan = build_plan(default_layout(), args.seed)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=1) + "\n")
    edges, intersections = plan["edges"], plan["intersections"]
    lanes = sum(len(e["lanes"]) for e in edges)
    controls = [i["control"] for i in intersections]
    print(
        f"wrote {out}: {len(plan['nodes'])} nodes, {len(edges)} edges, {lanes} lanes, "
        f"{controls.count('signal')} signalised, {controls.count('stop')} all-way stop, "
        f"{len(plan['blocks'])} blocks, {len(plan['parcels'])} parcels, "
        f"{len(plan['pois'])} points of interest"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
