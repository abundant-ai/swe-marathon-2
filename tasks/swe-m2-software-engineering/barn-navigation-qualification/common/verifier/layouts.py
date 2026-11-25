"""Authored clutter layouts and a measured BARN challenge asset crop."""

from world_reference import CYLINDERS


def raster(width, height, occupied):
    """Make a reusable occupancy raster in the stated y-up convention."""
    return ["".join("#" if (x,y) in occupied else "." for x in range(width)) for y in range(height)]


def course(kind):
    """Build a staged route, dynamic shutter, or authentic obstacle-grid adaptation."""
    w,h=24,15
    occupied={(7,y) for y in range(h) if y not in (6,11)}
    occupied|={(13,y) for y in range(h) if y not in (3,10)}
    occupied|={(18,y) for y in range(h) if y not in (5,12)}
    occupied|={(10,8),(10,9),(11,9),(16,4),(16,5),(20,9),(21,9)}
    spec={"rows":raster(w,h,occupied),"resolution_m":0.31,"start":[2,6],"goal":[21,7],
          "radius_m":0.122,"margin_m":0.016,"dt":0.12,"max_v":0.52,"max_w":1.26,
          "goal_tolerance_m":0.076,"deadline":315}
    if kind=="barn":
        w,h=29,29
        obstacles={(int(round((x+4.425)/0.15)),int(round((y-5.175)/0.15))) for _,x,y in CYLINDERS}
        spec|={"rows":raster(w,h,obstacles),"resolution_m":0.15,"start":[8,4],"goal":[20,23],
               "radius_m":0.198,"margin_m":0.020,"deadline":275}
    elif kind in ("sealed","release"):
        for y in range(h):
            occupied.add((7,y))
        spec["rows"]=raster(w,h,occupied)
        if kind=="sealed":
            spec["deadline"]=100
        else:
            spec["deadline"]=340
    elif kind=="pinch":
        w,h=17,11
        occupied={(x,y) for x in range(w) for y in range(h) if x in (0,w-1) or y in (0,h-1)}
        occupied|={(8,y) for y in range(1,h-1) if y!=5}
        spec|={"rows":raster(w,h,occupied),"start":[2,5],"goal":[14,5],"radius_m":0.136,
               "margin_m":0.025,"deadline":105}
    return spec


def revised(spec, remove=(), add=()):
    """Produce a complete occupancy refresh while preserving map and dimensions."""
    rows=[list(r) for r in spec["rows"]]
    for x,y in remove:
        rows[y][x]="."
    for x,y in add:
        rows[y][x]="#"
    return ["".join(r) for r in rows]
