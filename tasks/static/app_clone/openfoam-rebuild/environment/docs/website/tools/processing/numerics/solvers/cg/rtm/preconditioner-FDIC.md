<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/preconditioner-FDIC -->

# FDIC preconditioner

## Properties

* \<B\>F\</B\>aster version of the \<B\>D\</B\>iagonal\-based \<B\>I\</B\>ncomplete
\<B\>C\</B\>holesky preconditioner (symmetric equivalent of DILU)
* Symmetric matrices
* parallel inconsistent

## Usage

```
preconditioner  FDIC;

```

## Further information

Source code:

* [FDICPreconditioner](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/preconditioners/FDICPreconditioner)

API:

* [Foam::FDICPreconditioner](https://api.openfoam.com/2606/Foam_FDICPreconditioner.html)
