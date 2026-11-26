"""Render the staging-cell drawing sheets shipped under environment/resources/cell.

Each sheet is PostScript drawn here, rasterised by Ghostscript into an 8-bit
grey PNG, then reduced to IHDR, IDAT and IEND chunks so no text layer or
metadata survives. Geometry is deliberately not to scale: only the printed
dimensions carry the facts. Run with any Python 3.12+ that has Ghostscript
(`gs`) on PATH. Rebuilding must be byte-identical.
"""

import argparse
import struct
import subprocess
import sys
import tempfile
import zlib
from itertools import pairwise
from math import atan2, cos, degrees, hypot, radians, sin
from pathlib import Path

TASK = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(TASK / "common" / "verifier"))
import cell_truth as ct

WIDTH, HEIGHT = 1280, 900
OUT = TASK / "environment" / "resources" / "cell"
DEG = "°"

PROLOG = """%!PS-Adobe-3.0
<< /PageSize [1280 900] >> setpagedevice
1 setgray 0 0 1280 900 rectfill 0 setgray
1 setlinejoin 1 setlinecap
/Helvetica findfont dup length dict begin { 1 index /FID ne { def } { pop pop } ifelse }
  forall /Encoding ISOLatin1Encoding def currentdict end /HelvL exch definefont pop
/Helvetica-Bold findfont dup length dict begin { 1 index /FID ne { def } { pop pop } ifelse }
  forall /Encoding ISOLatin1Encoding def currentdict end /HelvLB exch definefont pop
/F { /HelvL findfont exch scalefont setfont } def
/FB { /HelvLB findfont exch scalefont setfont } def
/ct { 3 1 roll moveto dup stringwidth pop -2 div 0 rmoveto show } def
/lt { 3 1 roll moveto show } def
/rt { 3 1 roll moveto dup stringwidth pop neg 0 rmoveto show } def
/kt { /sz exch def /s exch def /yy exch def /xx exch def
      s stringwidth pop /w exch def
      gsave 1 setgray xx w 2 div sub 5 sub yy sz 0.3 mul sub w 10 add sz 1.15 mul rectfill grestore
      xx w 2 div sub yy moveto s show } def
/ah { gsave 3 1 roll translate rotate newpath 0 0 moveto -18 5.5 lineto
      -18 -5.5 lineto closepath fill grestore } def
/solid { [] 0 setdash } def
/phantom { [26 7 7 7 7 7] 0 setdash } def
/hidden { [12 8] 0 setdash } def
"""


def fmt(value):
    """Print a drawing number with one decimal place."""
    return f"{value:.1f}"


def esc(text):
    """Escape a PostScript string literal."""
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class Sheet:
    """Accumulate PostScript drawing commands for one sheet."""

    def __init__(self):
        self.ops = [PROLOG]

    def add(self, text):
        self.ops.append(text)

    def line(self, a, b, w=2.0, style="solid"):
        self.add(
            f"{style} {w} setlinewidth newpath {a[0]:.2f} {a[1]:.2f} moveto "
            f"{b[0]:.2f} {b[1]:.2f} lineto stroke solid"
        )

    def poly(self, points, w=2.0, style="solid", close=True):
        path = " ".join(
            f"{x:.2f} {y:.2f} {'moveto' if i == 0 else 'lineto'}"
            for i, (x, y) in enumerate(points)
        )
        end = "closepath " if close else ""
        self.add(f"{style} {w} setlinewidth newpath {path} {end}stroke solid")

    def rect(self, x, y, w, h, lw=2.0, style="solid"):
        self.poly([(x, y), (x + w, y), (x + w, y + h), (x, y + h)], lw, style)

    def fill_rect(self, x, y, w, h, grey=0.82):
        self.add(
            f"gsave {grey} setgray {x:.2f} {y:.2f} {w:.2f} {h:.2f} rectfill grestore"
        )

    def circle(self, c, r, w=2.0, style="solid", fill=False):
        op = "fill" if fill else "stroke"
        self.add(
            f"{style} {w} setlinewidth newpath {c[0]:.2f} {c[1]:.2f} {r} 0 360 arc "
            f"closepath {op} solid"
        )

    def text(self, p, s, size=22, align="ct", bold=False, angle=0.0, knock=False):
        font = "FB" if bold else "F"
        show = f"({esc(s)}) {size} kt" if knock else f"({esc(s)}) {align}"
        if angle:
            self.add(
                f"gsave {p[0]:.2f} {p[1]:.2f} translate {angle:.3f} rotate {size} {font} "
                f"0 0 {show} grestore"
            )
        else:
            self.add(f"{size} {font} {p[0]:.2f} {p[1]:.2f} {show}")

    def lines(self, p, rows, size=20, step=28):
        for i, row in enumerate(rows):
            self.text((p[0], p[1] - i * step), row, size, align="lt")

    def arrow(self, tip, angle):
        self.add(f"{tip[0]:.2f} {tip[1]:.2f} {angle:.3f} ah")

    def vector(self, origin, angle, length, label, w=3.0, size=22, label_gap=24):
        tip = (
            origin[0] + length * cos(radians(angle)),
            origin[1] + length * sin(radians(angle)),
        )
        self.line(origin, tip, w)
        self.arrow(tip, angle)
        off = (
            tip[0] + label_gap * cos(radians(angle)),
            tip[1] + label_gap * sin(radians(angle)) - size * 0.35,
        )
        self.text(off, label, size, bold=True)
        return tip

    def ext(self, start, end, gap=6):
        """Extension line from a feature point toward a dimension line, with gaps."""
        dx, dy = end[0] - start[0], end[1] - start[1]
        length = hypot(dx, dy)
        if length < 1:
            return
        ux, uy = dx / length, dy / length
        self.line(
            (start[0] + ux * gap, start[1] + uy * gap),
            (end[0] + ux * 10, end[1] + uy * 10),
            1.1,
        )

    def hdim(self, p1, p2, y, label, size=22, style="solid", ext=True):
        """Horizontal dimension between the x positions of p1 and p2, drawn at height y."""
        a, b = (p1[0], y), (p2[0], y)
        if ext:
            self.ext(p1, a)
            self.ext(p2, b)
        self.line(a, b, 1.4, style)
        sense = 0 if b[0] > a[0] else 180
        self.arrow(b, sense)
        self.arrow(a, sense + 180)
        self.text(((a[0] + b[0]) / 2, y + 7), label, size, knock=True)

    def vdim(self, p1, p2, x, label, size=22, ext=True):
        """Vertical dimension between the y positions of p1 and p2, drawn at x."""
        a, b = (x, p1[1]), (x, p2[1])
        if ext:
            self.ext(p1, a)
            self.ext(p2, b)
        self.line(a, b, 1.4)
        sense = 90 if b[1] > a[1] else -90
        self.arrow(b, sense)
        self.arrow(a, sense + 180)
        self.text((x - 7, (a[1] + b[1]) / 2), label, size, angle=90, knock=True)

    def angular(self, centre, radius, start, stop, label, size=22, text_radius=None):
        """Angular dimension arc from start to stop (degrees, counter-clockwise)."""
        self.add(
            f"solid 1.4 setlinewidth newpath {centre[0]:.2f} {centre[1]:.2f} {radius} "
            f"{start:.3f} {stop:.3f} arc stroke"
        )
        for a, sense in ((stop, 90), (start, -90)):
            tip = (
                centre[0] + radius * cos(radians(a)),
                centre[1] + radius * sin(radians(a)),
            )
            self.arrow(tip, a + sense)
        mid = radians((start + stop) / 2)
        r = text_radius or radius + 34
        pos = (centre[0] + r * cos(mid), centre[1] + r * sin(mid) - size * 0.35)
        self.text(pos, label, size, knock=True)

    def cloud(self, x, y, w, h, bump=13):
        """Revision cloud: scalloped outline around a rectangle."""
        corners = [(x, y), (x + w, y), (x + w, y + h), (x, y + h)]
        ops = ["solid 1.6 setlinewidth"]
        for i in range(4):
            a, b = corners[i], corners[(i + 1) % 4]
            n = max(2, round(hypot(b[0] - a[0], b[1] - a[1]) / (2 * bump)))
            heading = degrees(atan2(b[1] - a[1], b[0] - a[0]))
            r = hypot(b[0] - a[0], b[1] - a[1]) / n / 2
            for k in range(n):
                cx = a[0] + (b[0] - a[0]) * (k + 0.5) / n
                cy = a[1] + (b[1] - a[1]) * (k + 0.5) / n
                ops.append(
                    f"newpath {cx:.2f} {cy:.2f} {r:.2f} {heading + 180:.2f} {heading:.2f} "
                    "arcn stroke"
                )
        self.add(" ".join(ops))

    def datum_target(self, p, name, box=(-50, 18), size=22):
        """Datum point: a crossed circle with a boxed letter."""
        self.circle(p, 11, 2)
        self.line((p[0] - 18, p[1]), (p[0] + 18, p[1]), 1.4)
        self.line((p[0], p[1] - 18), (p[0], p[1] + 18), 1.4)
        corner = (p[0] + box[0], p[1] + box[1])
        self.rect(corner[0], corner[1], 32, 32, 2)
        self.text((corner[0] + 16, corner[1] + 8), name, size, bold=True)

    def datum_plane(self, p, name, size=22):
        """Datum feature symbol on a floor line: a filled triangle and a boxed letter."""
        self.add(
            f"newpath {p[0] - 14:.2f} {p[1]:.2f} moveto {p[0] + 14:.2f} {p[1]:.2f} lineto "
            f"{p[0]:.2f} {p[1] + 20:.2f} lineto closepath fill"
        )
        self.line((p[0], p[1] + 20), (p[0], p[1] + 44), 1.6)
        self.rect(p[0] - 16, p[1] + 44, 32, 32, 2)
        self.text((p[0], p[1] + 52), name, size, bold=True)

    def floor(self, x0, x1, y):
        self.line((x0, y), (x1, y), 2.5)
        for x in range(int(x0) + 10, int(x1), 22):
            self.line((x, y), (x - 14, y - 14), 1.0)

    def station_mark(
        self, p, name, style="solid", void=False, align="rt", dx=-24, dy=20
    ):
        self.circle(p, 14, 2.5 if style == "solid" else 2, style)
        if void:
            self.line((p[0] - 12, p[1] - 12), (p[0] + 12, p[1] + 12), 1.8)
            self.line((p[0] - 12, p[1] + 12), (p[0] + 12, p[1] - 12), 1.8)
        else:
            self.line((p[0] - 22, p[1]), (p[0] + 22, p[1]), 1.1)
            self.line((p[0], p[1] - 22), (p[0], p[1] + 22), 1.1)
        if name:
            self.text((p[0] + dx, p[1] + dy), name, 24, align=align, bold=True)

    def triad(self, origin, labels=("X", "Y"), length=70):
        self.vector(origin, 0, length, labels[0], 2.5)
        self.vector(origin, 90, length, labels[1], 2.5)
        self.circle(origin, 4, 1, fill=True)

    def heading(self, text):
        self.text((40, 858), text, 26, align="lt", bold=True)

    def title_block(self, view, number, units="mm / deg"):
        x, y, w, h = 840, 18, 422, 118
        self.rect(x, y, w, h, 2.5)
        self.line((x, y + 76), (x + w, y + 76), 1.4)
        self.line((x, y + 40), (x + w, y + 40), 1.4)
        self.line((x + 290, y), (x + 290, y + 76), 1.4)
        self.text((x + w / 2, y + 86), "STAGING CELL B HANDOFF LAYOUT", 22, bold=True)
        self.text((x + 145, y + 48), view, 20)
        self.text((x + 356, y + 49), f"SHEET {number} OF 4", 18)
        self.text((x + 145, y + 11), f"{units}   NOT TO SCALE", 20)
        self.text((x + 356, y + 11), "REV C", 20, bold=True)
        x, y = 840, 142
        self.rect(x, y, 422, 74, 1.6)
        self.line((x, y + 37), (x + 422, y + 37), 1.2)
        self.line((x + 60, y), (x + 60, y + 74), 1.2)
        self.text((x + 30, y + 46), "B", 20)
        self.text((x + 76, y + 46), "ISSUED FOR TRIAL - VOID", 20, align="lt")
        self.text((x + 30, y + 9), "C", 20, bold=True)
        self.text((x + 76, y + 9), "STATION AND DWELL REVISED", 20, align="lt")

    def render(self):
        return "\n".join([*self.ops, "showpage", ""])


def plan_sheet():
    """S1: plan view of H1, H2, N1 and the void revision B station."""
    s = Sheet()
    s.heading("PLAN - STAGING CELL B, LOOKING DOWN -Z")
    a, p1, h1 = (600, 450), (200, 270), (420, 360)
    h2, h0, f, n1 = (700, 540), (300, 620), (820, 620), (1000, 730)

    # Datum A and the dowel P1 that the station chain starts from.
    s.datum_target(a, "A", box=(-52, 16))
    s.circle(p1, 10, 2)
    s.circle(p1, 3, 1, fill=True)
    s.text((p1[0] + 8, p1[1] - 40), "P1", 22, bold=True)
    s.hdim(p1, a, 150, fmt(-ct.DOWEL_P1_MM[0]))
    s.vdim(p1, a, 80, fmt(-ct.DOWEL_P1_MM[1]))

    # Station H1, located from P1, with its grip axis Xs.
    s.station_mark(h1, "H1", dx=-22, dy=22)
    s.hdim(p1, h1, 205, fmt(ct.STATION_MM[0] - ct.DOWEL_P1_MM[0]))
    s.vdim(p1, h1, 135, fmt(ct.STATION_MM[1] - ct.DOWEL_P1_MM[1]))
    s.line((h1[0] + 24, h1[1]), (h1[0] + 150, h1[1]), 1.2, "phantom")
    s.vector(h1, ct.STATION_YAW_DEG, 165, "Xs")
    s.angular(
        h1, 100, 0, ct.STATION_YAW_DEG, fmt(ct.STATION_YAW_DEG) + DEG, text_radius=132
    )

    # Raised alternate H2, located from datum A.
    h2_mm = [x + d for x, d in zip(ct.STATION_MM, ct.RAISED_OFFSET_MM, strict=True)]
    s.station_mark(h2, "H2", style="phantom", dx=-24, dy=18)
    s.hdim(a, h2, 600, fmt(h2_mm[0]))
    s.vdim(a, h2, 755, fmt(h2_mm[1]))

    # Void revision B station inside a revision cloud.
    s.station_mark(h0, None, style="hidden", void=True)
    s.text((h0[0] + 6, h0[1] + 30), "H1 REV B - VOID", 20)
    s.hdim(h0, h1, 572, fmt(ct.STATION_MM[0] - ct.SUPERSEDED_STATION_MM[0]))
    s.vdim(h1, h0, 255, fmt(ct.SUPERSEDED_STATION_MM[1] - ct.STATION_MM[1]))
    s.cloud(196, 540, 262, 160)

    # Nest plate with corner F, and the nest N1 located from F.
    s.rect(f[0], f[1], 380, 180, 2.5)
    s.text((f[0] + 12, f[1] - 30), "F", 24, align="lt", bold=True)
    s.text((f[0] + 16, f[1] + 150), "NEST PLATE", 20, align="lt")
    s.hdim(a, f, 395, fmt(ct.PLATE_F_MM[0]))
    s.vdim(a, f, 800, fmt(ct.PLATE_F_MM[1]))
    s.circle(n1, 13, 2.5)
    s.circle(n1, 3, 1, fill=True)
    s.text((n1[0] + 22, n1[1] + 14), "N1", 24, align="lt", bold=True)
    s.hdim(f, n1, 838, fmt(ct.NEST_MM[0] - ct.PLATE_F_MM[0]))
    s.vdim(f, n1, 1240, fmt(ct.NEST_MM[1] - ct.PLATE_F_MM[1]))
    s.text((f[0] + 190, f[1] + 22), "ORIENTATION: DETAIL D, SHEET 3", 20)

    s.triad((690, 262))
    s.lines(
        (950, 330),
        [
            "WORLD ORIGIN AT DATUM A.",
            "HEIGHTS: SHEETS 2 AND 3.",
            "H2 KEEPS THE H1 ORIENTATION.",
            "LEFT ARM BASE OFF SHEET -Y,",
            "RIGHT ARM BASE OFF SHEET +Y.",
        ],
        size=18,
        step=26,
    )
    s.title_block("PLAN", 1)
    return s


def gripped_bar(s, centre, tilt, style):
    """Draw the payload bar with a gripper block at each end, tilted by tilt degrees."""
    half = 175
    ux, uy = cos(radians(tilt)), sin(radians(tilt))

    def at(along, across):
        return (
            centre[0] + along * ux - across * uy,
            centre[1] + along * uy + across * ux,
        )

    s.poly([at(-half, 14), at(half, 14), at(half, -14), at(-half, -14)], 2.2, style)
    for end in (-half, half):
        s.poly(
            [at(end - 16, -30), at(end + 16, -30), at(end + 16, 30), at(end - 16, 30)],
            2.0,
            style,
        )
    return at(-half, 0), at(half, 0)


def section_sheet():
    """S2: section A-A along the station's horizontal Ys axis."""
    s = Sheet()
    s.heading("SECTION A-A - LOOKING ALONG +Ys, Xs TO THE RIGHT, Z UP")
    floor_y = 150
    s.floor(70, 800, floor_y)
    s.datum_plane((110, floor_y), "B")
    h1, h2, h0 = (440, 470), (500, 700), (740, 330)
    tilt = 16.0  # drawn angle, exaggerated on purpose
    left, right = gripped_bar(s, h1, tilt, "solid")
    s.station_mark(h1, "H1", dx=0, dy=40, align="ct")
    s.text((left[0] + 20, left[1] - 70), "LEFT GRIPPER", 20)
    s.text((right[0] + 10, right[1] - 74), "RIGHT GRIPPER", 20)
    gripped_bar(s, h2, tilt, "phantom")
    s.station_mark(h2, "H2", style="phantom", dx=0, dy=40, align="ct")
    s.vector(
        (right[0] + 20 * cos(radians(tilt)), right[1] + 20 * sin(radians(tilt))),
        tilt,
        70,
        "Xs",
    )
    s.line((h1[0] + 24, h1[1]), (h1[0] + 300, h1[1]), 1.2, "phantom")
    s.angular(h1, 250, 0, tilt, fmt(-ct.STATION_PITCH_DEG) + DEG, text_radius=290)
    s.vdim((70, floor_y), h1, 200, fmt(ct.STATION_MM[2]), ext=False)
    s.ext(h1, (200, h1[1]))
    s.vdim(h1, h2, 200, fmt(ct.RAISED_OFFSET_MM[2]), ext=False)
    s.ext(h2, (200, h2[1]))
    # Void revision B station height.
    s.station_mark(h0, None, style="hidden", void=True)
    s.text((h0[0] + 30, h0[1] - 8), "H1 REV B - VOID", 20, align="lt")
    s.vdim((800, floor_y), h0, 690, fmt(ct.SUPERSEDED_STATION_MM[2]), ext=False)
    s.ext(h0, (690, h0[1]))
    s.cloud(650, 284, 310, 92)
    s.lines(
        (880, 640),
        [
            "Ys = Z x Xs, HORIZONTAL.",
            "Xs RUNS FROM THE LEFT",
            "GRIP TO THE RIGHT GRIP.",
            "H2 KEEPS THE H1 ORIENTATION.",
        ],
        size=18,
        step=26,
    )
    s.title_block("SECTION A-A", 2)
    return s


def nest_sheet():
    """S3: detail D, nest N1 orientation in plan, view B-B and view C-C."""
    s = Sheet()
    s.heading("DETAIL D - NEST N1 ORIENTATION")
    # Plan on N1: yaw of the nest x axis from world +X.
    s.text((60, 800), "PLAN ON N1", 22, align="lt", bold=True)
    n = (170, 560)
    s.station_mark(n, "N1", dx=-22, dy=-40)
    s.line((n[0] + 20, n[1]), (n[0] + 260, n[1]), 1.2, "phantom")
    s.vector(n, ct.NEST_YAW_DEG, 170, "Xn")
    s.angular(n, 120, 0, ct.NEST_YAW_DEG, fmt(ct.NEST_YAW_DEG) + DEG, text_radius=156)
    s.triad((70, 640), length=60)

    # View B-B: looking along +Y' (after yaw), Xn' to the right, Z up.
    s.text((560, 800), "VIEW B-B - ALONG +Y' AFTER YAW", 22, align="lt", bold=True)
    floor_y = 470
    s.floor(540, 1240, floor_y)
    s.datum_plane((580, floor_y), "B")
    nb = (820, 650)
    tilt = 24.0  # drawn angle, exaggerated on purpose
    ux, uy = cos(radians(tilt)), sin(radians(tilt))
    seat = [(-110, -36), (110, -36), (110, 0), (-110, 0)]
    s.poly([(nb[0] + x * ux - y * uy, nb[1] + x * uy + y * ux) for x, y in seat], 2.2)
    s.station_mark(nb, None)
    s.text((nb[0] - 30, nb[1] + 30), "N1", 24, align="rt", bold=True)
    s.line((nb[0] + 24, nb[1]), (nb[0] + 330, nb[1]), 1.2, "phantom")
    s.vector(nb, tilt, 250, "Xn")
    s.angular(nb, 210, 0, tilt, fmt(-ct.NEST_PITCH_DEG) + DEG, text_radius=250)
    s.vdim((540, floor_y), nb, 680, fmt(ct.NEST_MM[2]), ext=False)
    s.ext(nb, (680, nb[1]))

    # View C-C: Xn toward the viewer; roll of Yn from the horizontal.
    s.text((60, 410), "VIEW C-C - Xn TOWARD VIEWER", 22, align="lt", bold=True)
    c = (230, 215)
    roll = -11.0  # drawn angle, exaggerated on purpose
    s.circle(c, 16, 2.5)
    s.circle(c, 4, 1, fill=True)
    s.text((c[0] - 26, c[1] - 40), "Xn", 22, align="rt", bold=True)
    s.line((c[0] + 22, c[1]), (c[0] + 300, c[1]), 1.2, "phantom")
    s.line((c[0], c[1] + 22), (c[0], c[1] + 120), 1.2, "phantom")
    s.vector(c, roll, 230, "Yn")
    s.vector(c, 90 + roll, 110, "Zn")
    s.angular(c, 190, roll, 0, fmt(-ct.NEST_ROLL_DEG) + DEG, text_radius=222)

    s.lines(
        (560, 360),
        [
            "ROTATIONS APPLY IN THIS ORDER:",
            "YAW ABOUT Z, THEN PITCH ABOUT Y',",
            "THEN ROLL ABOUT X''.",
            "N1 POSITION: SHEET 1 AND VIEW B-B.",
        ],
        size=18,
        step=26,
    )
    s.title_block("DETAIL D", 3)
    return s


def timing_x(ms):
    """Piecewise map from milliseconds to the page; deliberately not to scale."""
    knots = [(0, 300), (160, 450), (800, 930), (900, 1030), (1000, 1150)]
    for (m0, x0), (m1, x1) in pairwise(knots):
        if ms <= m1:
            return x0 + (x1 - x0) * (ms - m0) / (m1 - m0)
    return knots[-1][1]


def timing_sheet():
    """S4: gripper timing during the handoff and the controller tick."""
    s = Sheet()
    s.heading("HANDOFF TIMING - BOTH GRIPPERS")
    at = timing_x
    axis_y = 430
    s.line((at(0) - 30, axis_y), (at(1000) + 60, axis_y), 2.2)
    s.arrow((at(1000) + 60, axis_y), 0)
    s.text((at(1000) + 74, axis_y - 8), "t", 24, align="lt", bold=True)
    s.line((at(0), axis_y - 10), (at(0), axis_y + 10), 2)
    s.text((at(0) - 14, axis_y + 16), "T0", 22, align="rt", bold=True)

    lanes = (
        ("LEFT GRIPPER", 640, 0, ct.DWELL_END_MS),
        ("RIGHT GRIPPER", 540, ct.DWELL_START_MS, 1000),
    )
    for name, y, t0, t1 in lanes:
        s.text((at(0) - 40, y - 8), name, 20, align="rt", bold=True)
        s.fill_rect(at(t0), y - 26, at(t1) - at(t0), 52)
        s.rect(at(t0), y - 26, at(t1) - at(t0), 52, 2)
        s.text(((at(t0) + at(t1)) / 2, y - 8), "CLOSED", 20, bold=True)
        if t0 > 0:
            s.text(((at(0) + at(t0)) / 2, y - 8), "OPEN", 20)
        if t1 < 1000:
            s.text(((at(t1) + at(1000)) / 2, y - 8), "OPEN", 20)
    for ms in (ct.DWELL_START_MS, ct.DWELL_END_MS):
        s.line((at(ms), axis_y + 8), (at(ms), 690), 1.1, "hidden")
    # Dwell bracket.
    y0, y1 = at(ct.DWELL_START_MS), at(ct.DWELL_END_MS)
    s.poly([(y0, 686), (y0, 706), (y1, 706), (y1, 686)], 2, close=False)
    s.text(((y0 + y1) / 2, 716), "TRANSFER DWELL", 22, bold=True)
    # Event times, dimensioned from T0.
    s.hdim(
        (at(0), axis_y), (at(ct.DWELL_START_MS), axis_y), 365, str(ct.DWELL_START_MS)
    )
    s.hdim((at(0), axis_y), (at(ct.DWELL_END_MS), axis_y), 305, str(ct.DWELL_END_MS))
    # Void revision B dwell.
    rb0, rb1 = ct.SUPERSEDED_DWELL_MS
    s.hdim(
        (at(rb0), 0), (at(rb1), 0), 790, f"{rb0} TO {rb1}", style="phantom", ext=False
    )
    s.text((at(rb1) + 24, 783), "REV B DWELL - VOID", 20, align="lt")
    s.cloud(at(0) - 24, 758, at(rb1) - at(0) + 300, 72)

    # Detail E: one controller tick.
    s.text((60, 250), "DETAIL E - CONTROLLER CLOCK", 22, align="lt", bold=True)
    y = 140
    s.line((70, y), (560, y), 2)
    for k in range(8):
        x = 90 + 64 * k
        s.line((x, y), (x, y + 22), 2)
    s.hdim((154, y + 22), (218, y + 22), y + 64, str(ct.TICK_MS))
    s.text((186, y - 38), "1 TICK", 20, bold=True)
    s.lines(
        (580, 250),
        [
            "ALL TIMES IN ms FROM T0,",
            "THE START OF THE HANDOFF.",
            "BOTH GRIPPERS STAY",
            "CLOSED FOR THE DWELL.",
        ],
        size=18,
        step=26,
    )
    s.title_block("TIMING", 4, units="ms")
    return s


def build(sheet):
    """Rasterise a sheet to a stripped PNG byte string."""
    with tempfile.TemporaryDirectory() as tmp:
        ps = Path(tmp, "sheet.ps")
        png = Path(tmp, "sheet.png")
        ps.write_text(sheet.render(), encoding="latin-1")
        subprocess.run(
            [
                "gs",
                "-q",
                "-dSAFER",
                "-dBATCH",
                "-dNOPAUSE",
                "-sDEVICE=pnggray",
                "-r72",
                "-dTextAlphaBits=4",
                "-dGraphicsAlphaBits=4",
                f"-sOutputFile={png}",
                str(ps),
            ],
            check=True,
        )
        return strip(png.read_bytes())


def strip(data):
    """Keep only IHDR, IDAT and IEND chunks of a PNG stream."""
    signature = b"\x89PNG\r\n\x1a\n"
    if data[:8] != signature:
        raise ValueError("not a PNG")
    out, i = [signature], 8
    while i < len(data):
        (length,) = struct.unpack(">I", data[i : i + 4])
        kind = data[i + 4 : i + 8]
        chunk = data[i : i + 12 + length]
        if kind in (b"IHDR", b"IDAT", b"IEND"):
            body = chunk[8:-4]
            if zlib.crc32(kind + body) != struct.unpack(">I", chunk[-4:])[0]:
                raise ValueError("bad CRC")
            out.append(chunk)
        i += 12 + length
    return b"".join(out)


SHEETS = {
    "cell-sheet-1.png": plan_sheet,
    "cell-sheet-2.png": section_sheet,
    "cell-sheet-3.png": nest_sheet,
    "cell-sheet-4.png": timing_sheet,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=OUT)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    for name, make in SHEETS.items():
        (args.out / name).write_bytes(build(make()))
        print(args.out / name)


if __name__ == "__main__":
    main()
