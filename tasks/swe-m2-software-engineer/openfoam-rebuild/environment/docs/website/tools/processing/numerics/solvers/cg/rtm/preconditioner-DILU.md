<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/preconditioner-DILU -->

# DILU preconditioner

## Properties

* Asymmetric matrices
* Simplified \<B\>D\</B\>iagonal\-based \<B\>I\</B\>ncomplete \<B\>LU\</B\> preconditioner
* Parallel inconsistent

## Usage

```
preconditioner  DILU;

```

## Further information

Source code:

* [DILUPreconditioner](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/preconditioners/DILUPreconditioner)

API:

* [Foam::DILUPreconditioner](https://api.openfoam.com/2606/Foam_DILUPreconditioner.html)
