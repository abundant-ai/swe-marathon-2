"""Dev script: build mutant binaries of the legacy solver (text patches) into experiment/mutants/<name>/."""

import os, shutil, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FC = os.environ["FC"]
MUT = {
    "m1_no_dt_smoothing": (
        "tstep.f",
        "      DTNEW = SMOOTH*DTOLD + (1.0D0-SMOOTH)*DTRAW\n",
        "      DTNEW = DTRAW\n",
    ),
    "m2_ramp_off_by_one": ("io.f", "      IWARM = 20\n", "      IWARM = 19\n"),
    "m3_corner_rule_swap": (
        "bc.f",
        "               IF (J .LT. JMAX .AND. FLAG(I,J+1)+FLAG(I+1,J+1) .EQ. 2)\n     &            THEN\n                  U(I,J) = -U(I,J+1)\n               ELSEIF (J .GT. 1 .AND. FLAG(I,J-1)+FLAG(I+1,J-1) .EQ. 2)\n     &            THEN\n                  U(I,J) = -U(I,J-1)",
        "               IF (J .GT. 1 .AND. FLAG(I,J-1)+FLAG(I+1,J-1) .EQ. 2)\n     &            THEN\n                  U(I,J) = -U(I,J-1)\n               ELSEIF (J .LT. JMAX .AND. FLAG(I,J+1)+FLAG(I+1,J+1) .EQ. 2)\n     &            THEN\n                  U(I,J) = -U(I,J+1)",
    ),
    "m4_decay_0p9": ("readin.f", "      DECAY = 0.98D0\n", "      DECAY = 0.9D0\n"),
    "m5_freeslip_west": (
        "bc.f",
        "         IF (IBCW .EQ. 1) THEN\n            V(0,J) = -V(1,J)\n         ELSE\n            V(0,J) = V(1,J)",
        "         IF (IBCW .EQ. 1) THEN\n            V(0,J) = -V(1,J)\n         ELSE\n            V(0,J) = -V(1,J)",
    ),
    "m6_buoy_cell_only": (
        "fg.f",
        "GT + BUOY*0.5D0*(TEM(I,J)+TEM(I,J+1))",
        "GT + BUOY*TEM(I,J)",
    ),
    "m7_sor_ji_order": (
        "poiss.f",
        "         DO 20 J = 1, JMAX\n            DO 10 I = 1, IMAX\n               IF (FLAG(I,J) .EQ. 0) GOTO 10\n               EW",
        "         DO 20 I = 1, IMAX\n            DO 10 J = 1, JMAX\n               IF (FLAG(I,J) .EQ. 0) GOTO 10\n               EW",
    ),
    "m8_thermal_dt_off": (
        "tstep.f",
        "      IF (ITEMP .NE. 0) DTRAW = MIN(DTRAW,",
        "      IF (ITEMP .EQ. 99) DTRAW = MIN(DTRAW,",
    ),
    "m9_resid_norm_all": (
        "poiss.f",
        "SQRT(RES/DBLE(NFLUID))",
        "SQRT(RES/DBLE(IMAX*JMAX))",
    ),
    "m10_restart_no_warm": ("io.f", "      IWARM = 20\n", "      IWARM = 0\n"),
}
for name, (f, a, b) in MUT.items():
    d = os.path.join(ROOT, "experiment", "mutants", name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(
        os.path.join(ROOT, "legacy"),
        d,
        ignore=shutil.ignore_patterns("nsflow", "decks"),
    )
    p = os.path.join(d, f)
    s = open(p).read()
    if s.count(a) != 1:
        print("PATCH FAILED", name, s.count(a))
        continue
    open(p, "w").write(s.replace(a, b))
    srcs = [x for x in os.listdir(d) if x.endswith(".f")]
    r = subprocess.run(
        [
            FC,
            "-O2",
            "-ffp-contract=off",
            "-std=legacy",
            "-ffixed-line-length-none",
            "-I.",
            "-o",
            "nsflow",
        ]
        + sorted(srcs),
        cwd=d,
        capture_output=True,
        text=True,
    )
    print(
        name,
        "built"
        if os.path.exists(os.path.join(d, "nsflow"))
        else "FAILED\n" + r.stderr[-300:],
    )
