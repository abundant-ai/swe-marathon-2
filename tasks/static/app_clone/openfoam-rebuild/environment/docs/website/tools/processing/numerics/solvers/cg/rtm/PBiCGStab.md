<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/PBiCGStab -->

# Stabilised preconditioned bi\-conjugate gradient (PBiCGStab)

## Properties

* symmetric and asymmetric matrices
* run\-time selectable [preconditioner](../index.md#preconditioners)
* good parallel scaling

## Usage

```
solver          PBiCGStab;
preconditioner  <conditioner>;
relTol          <relative tolerance>;
tolerance       <absolute tolerance>;

```

## Details

### Operation

### Computation cost

Start\-up

* 1 matrix\-vector multiply
* 1 parallel reduction

Per iteration

* 2 matrix\-vector multiplies
* 6 parallel reductions
* and preconditioner \- applied 2x

## Further information

Source code:

* [PBiCGStab](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/solvers/PBiCGStab)

API:

* [Foam::PBiCGStab](https://api.openfoam.com/2606/Foam_PBiCGStab.html)

References:

* *Van der Vorst* [81](../../../../../../references.md#van_der_vorst_bi-cgstab:_1992)
* *Barrett et al.* [5](../../../../../../references.md#barrett_templates_1994)
