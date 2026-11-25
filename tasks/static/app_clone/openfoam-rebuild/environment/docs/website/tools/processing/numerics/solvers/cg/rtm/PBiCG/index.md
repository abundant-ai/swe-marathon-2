<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/PBiCG/ -->

# Preconditioned bi\-conjugate gradient (PBiCG)

## Properties

* asymmetric matrices
* run\-time selectable [preconditioner](../../index.md#preconditioners)
* good parallel scaling

## Usage

```
solver          PBiCG;
preconditioner  <conditioner>;
relTol          <relative tolerance>;
tolerance       <absolute tolerance>;

```

## Details

### Operation

### Computation cost

Start\-up

* 2 matrix\-vector multiplies
* 1 parallel reduction

Per iteration

* 2 matrix\-vector multiplies
* 3 parallel reductions
* and preconditioner \- applied 2x

## Further information

Source code:

* [PBiCG](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/solvers/PBiCG)

API:

* [Foam::PBiCG](https://api.openfoam.com/2606/Foam_PBiCG.html)
