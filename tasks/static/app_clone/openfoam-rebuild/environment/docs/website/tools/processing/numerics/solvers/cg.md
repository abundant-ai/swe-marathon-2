<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg -->

# Conjugate gradient solvers

## Options

* [Preconditioned bi\-conjugate gradient (PBiCG)](cg/rtm/PBiCG.md)
* [Preconditioned conjugate gradient (PCG)](cg/rtm/PCG.md)
* [Stabilised preconditioned bi\-conjugate gradient (PBiCGStab)](cg/rtm/PBiCGStab.md)

## Preconditioners

Preconditioners manipulate the matrix equation to a form that is more readily
solved:

AP−1Px\=b A P^{\-1} P \\vec{x} \= \\vec{b}AP−1Px\=b
* [Diagonal preconditioner](cg/rtm/preconditioner-diagonal.md)
* [DIC preconditioner](cg/rtm/preconditioner-DIC.md)
* [DILU preconditioner](cg/rtm/preconditioner-DILU.md)
* [FDIC preconditioner](cg/rtm/preconditioner-FDIC.md)
* [GAMG preconditioner](cg/rtm/preconditioner-GAMG.md)
