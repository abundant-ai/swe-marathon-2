<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/smooth/rtm/DICGaussSeidel -->

# DIC Gauss Seidel Smoother

## Properties

* Combined DIC/GaussSeidel smoother in which DIC smoothing is followed by
GaussSeidel to ensure that any "spikes" created by the DIC sweeps are
smoothed\-out
* Symmetric matrices

## Usage

```
smoother        DICGaussSeidel;

```

## Further information

Source code:

* [DICGaussSeidel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/matrices/lduMatrix/smoothers/DICGaussSeidel)

API:

* [Foam::DICGaussSeidelSmoother](https://api.openfoam.com/2606/Foam_DICGaussSeidelSmoother.html)
