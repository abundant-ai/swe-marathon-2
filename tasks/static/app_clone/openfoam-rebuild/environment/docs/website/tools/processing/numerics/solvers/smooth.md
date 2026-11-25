<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/smooth -->

# Smooth solvers

## Options

* [Smooth](smooth/rtm/smooth.md)

## Smoothers

* nonBlockingGaussSeidelSmoother: Variant of gaussSeidelSmoother that expects
processor boundary cells to be sorted last and so can block later

* [DIC Gauss Seidel Smoother](smooth/rtm/DICGaussSeidel.md)
* [DIC Smoother](smooth/rtm/DIC.md)
* [DILU Smoother](smooth/rtm/DILU.md)
* [Gauss Seidel Smoother](smooth/rtm/gaussSeidel.md)
* [Symmetric Gauss Seidel Smoother](smooth/rtm/symGaussSeidel.md)
