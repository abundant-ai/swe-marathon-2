<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/PCG -->

# Preconditioned conjugate gradient (PCG)

## Properties

* symmetric matrices
* run\-time selectable [preconditioner](../index.md#preconditioners)
* good parallel scaling

## Usage

```
solver          PCG;
preconditioner  <conditioner>;
relTol          <relative tolerance>;
tolerance       <tolerance>;

```

## Details

### Operation

### Computation cost

Start\-up:

* 1 matrix\-vector multiply
* 1 parallel reduction

Per iteration

* 1 matrix\-vector multiply
* 3 parallel reductions
* and preconditioner \- applied 1x

## Further information

Source code

* [PCG](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/solvers/PCG)

API:

* [Foam::PCG](https://api.openfoam.com/2606/Foam_PCG.html)
