<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/ -->

# Conjugate gradient solvers

## Options

* [Preconditioned bi\-conjugate gradient (PBiCG)](rtm/PBiCG.md)
* [Preconditioned conjugate gradient (PCG)](rtm/PCG.md)
* [Stabilised preconditioned bi\-conjugate gradient (PBiCGStab)](rtm/PBiCGStab.md)

## Preconditioners

Preconditioners manipulate the matrix equation to a form that is more readily
solved:

AP−1Px\=b A P^{\-1} P \\vec{x} \= \\vec{b}AP−1Px\=b
* [Diagonal preconditioner](rtm/preconditioner-diagonal.md)
* [DIC preconditioner](rtm/preconditioner-DIC.md)
* [DILU preconditioner](rtm/preconditioner-DILU.md)
* [FDIC preconditioner](rtm/preconditioner-FDIC.md)
* [GAMG preconditioner](rtm/preconditioner-GAMG.md)
