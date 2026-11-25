<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/multigrid/rtm/GAMG -->

# GAMG Solver

## Properties

* symmetric or asymmetric matrices
* run\-time selectable [smoother](../../smooth.md#smoothers)
* efficient transport of information across the solution domain
* moderate parallel scaling

## Usage

Many of the `GAMG` solver inputs can be omitted and left to their default values
such that the basic usage comprises:

```
solver                  GAMG;
smoother                <smoother>;
relTol                  <relative tolerance>;
tolerance               <absolute tolerance>;

```

For more complete control, the full set of input entries includes:

```
// Mandatory entries
solver                  GAMG;
smoother                <smoother>;
relTol                  <relative tolerance>;
tolerance               <absolute tolerance>;

// Optional entries and associated default values

// Agglomeration
cacheAgglomeration      yes;
nCellsInCoarsestLevel   10;
processorAgglomerator   <processor agglomeration method>;

// Solver
nPreSweeps              0;
preSweepsLevelMultiplier 1;
maxPreSweeps            4;
nPostSweeps             2;
postSweepsLevelMultiplier 1;
maxPostSweeps           4;
nFinestSweeps           2;
interpolateCorrection   no;
scaleCorrection         yes;  // Yes: symmetric No: Asymmetric
directSolveCoarsest     no;

```

## Details

### Operation

Coarsens using agglomeration

* face area pair (geometric)
* algebraic pair (numerical coefficients)

Agglomeration \- number of levels depends on

* number of cells at coarsest level
* hard\-limit of a maximum of 50 levels

V\-cycle

* optional pre\- and post\- solve smoothing at each level
* optional smoothing at finest level

Data exchange between levels:

* restriction: fine\-to\-coarse (summation)
* prolongation: coarse\-to\-fine (injection)

Coarsest level solved using either:

* direct solver
* [PCG](../../cg/rtm/PCG.md) (symmetric matrices)
* [PBiCGStab](../../cg/rtm/PBiCGStab.md) (asymmetric matrices)

The system becomes more difficult to solve with increasing coarse
levels due to the increasing amount of (explicit) processor contributions.
This requires an efficient
[pre\-conditioner](../../cg.md#preconditioners),
which are generally not parallel\-aware

### Computation cost

Start\-up:

* construction of agglomeration levels
* 1 matrix\-vector multiply
* 1 parallel reduction

Per iteration:

* 1 matrix\-vector multiply per level
* 1 parallel reduction per level
* 1 matrix\-vector multiply per V\-cycle per iteration (finest level)
* 1 parallel reduction per V\-cycle per iteration (finest level)
* and cost of coarsest level solution, e.g. using the [PCG](../../cg/rtm/PCG.md) solver

## Further information

Source code:

* [GAMG](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/solvers/GAMG)

API:

* [Foam::GAMGSolver](https://api.openfoam.com/2606/Foam_GAMGSolver.html)
