<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/rtm/faceLimited/ -->

# Face\-limited gradient scheme

## Properties

## Usage

The scheme is specified using:

```
gradSchemes
{
    default         none;
    grad(U)         faceLimited <scheme> <coefficient>;
}

```

The coefficient should be specified in the range zero to one, where values of

## Further information

Source code

* [Foam::fv::faceLimitedGrad](https://api.openfoam.com/2606/Foam_fv_faceLimitedGrad.html)

Mult\-directional form

* [faceMDLimited](../faceMDLimited.md)
