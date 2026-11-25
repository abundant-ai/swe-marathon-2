<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/sngrad/rtm/limited -->

# Limited surface\-normal gradient scheme

## Properties

* snGrad scheme with limited non\-orthogonal correction
* delta coefficients given by: nonOrthDeltaCoeffs
* explicit non\-orthogonal correction

## Usage

The scheme is specified using:

```
snGradSchemes
{
    default         none;
    grad(U)         limited <corrected scheme> <psi>;
}

```

`psi` coefficient between 0 and 1

* 0: no correction, equivalent to the [uncorrected](../index.md) scheme
* 1: full correction applied
* 0\.5: non\-orthogonal contribution does not exceed the orthogonal part

## Further information

Source code

* [Foam::fv::limitedSnGrad](https://api.openfoam.com/2606/Foam_fv_limitedSnGrad.html)
