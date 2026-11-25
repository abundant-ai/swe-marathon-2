<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/cg/rtm/preconditioner-GAMG -->

# GAMG preconditioner

## Properties

* \<B\>G\</B\>eometric agglomerated \<B\>A\</B\>lgebraic \<B\>M\</B\>ulti\<B\>G\</B\>rid
preconditioner
* Symmetric and asymmetric matrices
* Parallel inconsistent
* See [GAMG solver details](../../multigrid/rtm/GAMG.md)

## Usage

```
preconditioner  GAMG;
smoother        <smoother>;
relTol          <relatve tolerance>;
tolerance       <absolute tolerance>;

```

## Further information

Source code:

* [GAMGPreconditioner](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/preconditioners/GAMGPreconditioner)

API:

* [Foam::GAMGPreconditioner](https://api.openfoam.com/2606/Foam_GAMGPreconditioner.html)
