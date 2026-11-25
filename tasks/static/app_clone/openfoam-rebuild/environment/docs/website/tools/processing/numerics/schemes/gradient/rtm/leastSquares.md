<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/rtm/leastSquares -->

# Least\-squares gradient scheme

## Properties

The cell gradient is calculated using least squares:

## Usage

The scheme is specified using:

```
gradSchemes
{
    default         none;
    grad(U)         leastSquares;
}

```

## Further information

Source code

* [Foam::fv::leastSquaresGrad](https://api.openfoam.com/2606/Foam_fv_leastSquaresGrad.html)

See also

* pointCellsLeastSquares: employs a cell\-point\-cell stencil
* edgeCellsLeastSquares: employs a cell\-edge\-cell stencil
