<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/preconditioner-DIC -->

# DIC preconditioner

## Properties

* Simplified \<B\>D\</B\>iagonal\-based \<B\>I\</B\>ncomplete \<B\>C\</B\>holesky
preconditioner (symmetric equivalent of
[DILU](preconditioner-DILU.md)).
* Symmetric matrices
* Parallel inconsistent

## Usage

```
preconditioner  DIC;

```

## Further information

Source code:

* [DICPreconditioner](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/preconditioners/DICPreconditioner)

API:

* [Foam::DICPreconditioner](https://api.openfoam.com/2606/Foam_DICPreconditioner.html)
