<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/rtm/cellMDLimited -->

# Multi\-directional cell\-limited gradient scheme

## Properties

## Usage

The scheme is specified using:

```
gradSchemes
{
    default         none;
    grad(U)         cellMDLimited <scheme> <coefficient>;
}

```

The coefficient should be specified in the range zero to one, where values of

## Further information

Source code

* [Foam::fv::cellMDLimitedGrad](https://api.openfoam.com/2606/Foam_fv_cellMDLimitedGrad.html)
