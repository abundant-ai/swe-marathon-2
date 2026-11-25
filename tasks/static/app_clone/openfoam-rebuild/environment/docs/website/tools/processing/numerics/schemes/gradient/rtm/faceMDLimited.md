<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/rtm/faceMDLimited -->

# Multi\-directional face\-limited gradient scheme

## Properties

## Usage

The scheme is specified using:

```
gradSchemes
{
    default         none;
    grad(U)         faceMDLimited <scheme> <coefficient>;
}

```

The coefficient should be specified in the range zero to one, where values of

## Further information

Source code

* [Foam::fv::faceMDLimitedGrad](https://api.openfoam.com/2606/Foam_fv_faceMDLimitedGrad.html)
