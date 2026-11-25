<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/smooth/rtm/smooth -->

# Smooth

## Properties

* symmetric or asymmetric matrices
* run\-time selectable [smoother](../index.md#smoothers)

## Usage

```
solver          smooth;
smoother        <smoother>;
relTol          <relative tolerance>;
tolerance       <absolute tolerance>;

```

## Further information

Source code:

* [SmoothSolver](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/LduMatrix/Solvers/SmoothSolver)

API:

* [Foam::smoothSolver](https://api.openfoam.com/2606/Foam_smoothSolver.html)
