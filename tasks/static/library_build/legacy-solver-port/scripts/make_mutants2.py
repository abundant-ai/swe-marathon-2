"""Dev script: mutant binaries of legacy2 (NSFLOW 2) into experiment/mutants2/<name>/."""

import os, shutil, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FC = os.environ["FC"]
MUT = {
    "n1_weight_squared": (
        "rhsop.f",
        "      WGT(PE) = PE/(PE + AUP)\n",
        "      WGT(PE) = PE*PE/(PE*PE + AUP)\n",
    ),
    "n2_kp_0p1": ("step.f", "(ERRP/ERRN)**0.2D0", "(ERRP/ERRN)**0.1D0"),
    "n3_safety_0p8": ("step.f", "FAC = 0.9D0*", "FAC = 0.8D0*"),
    "n4_restart_keeps_errp": ("io.f", "      ERRP = 1.0D0\n", "      ERRP = 0.5D0\n"),
    "n5_err_scale_nofloor": (
        "step.f",
        "ERRN = EMAX/(1.0D-3 + UM)/TOL",
        "ERRN = EMAX/UM/TOL",
    ),
    "n6_no_diffusion_cap": (
        "step.f",
        "      DT = MIN(DTN, DTCAP, DTDIF)\n",
        "      DT = MIN(DTN, DTCAP)\n",
    ),
    "n7_freeslip_west": (
        "bc.f",
        "         IF (IBCW .EQ. 1) THEN\n            V(0,J) = -V(1,J)\n         ELSE\n            V(0,J) = V(1,J)",
        "         IF (IBCW .EQ. 1) THEN\n            V(0,J) = -V(1,J)\n         ELSE\n            V(0,J) = -V(1,J)",
    ),
    "n8_growth_cap_2": (
        "step.f",
        "IF (FAC .GT. 1.5D0) FAC = 1.5D0",
        "IF (FAC .GT. 2.0D0) FAC = 2.0D0",
    ),
    "n9_cap_uses_max_dx": (
        "step.f",
        "DTCAP = CFLMAX*MIN(DX,DY)/UM",
        "DTCAP = CFLMAX*MAX(DX,DY)/UM",
    ),
    "n10_corrector_weight": (
        "step.f",
        "UH = U0(I,J) + 0.5D0*DT*(RU0(I,J)+RU1(I,J))",
        "UH = U0(I,J) + 0.5D0*DT*(RU0(I,J)+RU1(I,J)) + 1.0D-3*DT*RU1(I,J)",
    ),
    "n11_line_order_swap": (
        "poiss.f",
        "            DO 30 I = IMAX-1, 1, -1\n               PH = DP(I) - CP(I)*PH\n               P(I,J) = (1.0D0-OMEGA)*P(I,J) + OMEGA*PH\n   30       CONTINUE\n            DO 99 JJ=1,1\n   99       CONTINUE\n",
        None,
    ),
}
MUT.pop("n11_line_order_swap")
for name, (f, a, b) in MUT.items():
    d = os.path.join(ROOT, "experiment", "mutants2", name)
    shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(
        os.path.join(ROOT, "legacy2"),
        d,
        ignore=shutil.ignore_patterns("nsflow", "decks"),
    )
    p = os.path.join(d, f)
    s = open(p).read()
    if s.count(a) != 1:
        print("PATCH FAILED", name, s.count(a))
        continue
    open(p, "w").write(s.replace(a, b))
    srcs = sorted(x for x in os.listdir(d) if x.endswith(".f"))
    subprocess.run(
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
        + srcs,
        cwd=d,
        capture_output=True,
        text=True,
    )
    print(name, "built" if os.path.exists(os.path.join(d, "nsflow")) else "FAILED")
