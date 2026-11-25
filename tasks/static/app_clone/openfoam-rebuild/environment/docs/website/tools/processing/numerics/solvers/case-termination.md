<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/case-termination -->

# Case termination

By default, cases will run until the time settings are achieved in the
case [controlDict](../../../../fundamentals/case-structure/controldict.md) dictionary.
Alternatively, the `residualControl` object can be added to the
[fvSolution](../../../../fundamentals/case-structure/fvsolution.md) dictionary to enable
additional controls. This operates in two modes:

## Steady state

To terminate the case when the initial residual of the field
equations falls below user\-specified threshold values for SIMPLE\-based
solvers:

```
residualControl
{
    p           1e-2;
    "(Ux Uy)"   1e-4;
    "(k|epsilon|omega)" 1e-4;
}

```

## Transient

To control the number of outer corrector iterations for PIMPLE\-based solvers:

```
// Maximum number of outer correctors
nOuterCorrectors    50;

residualControl
{
    "(U|k|epsilon|omega)"
    {
        relTol          0;
        tolerance       1e-4;
    }
}

```
