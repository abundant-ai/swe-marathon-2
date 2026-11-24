<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/sngrad/rtm/faceCorrected -->

# Face\-corrected surface\-normal gradient scheme

## Properties

* Central\-difference snGrad scheme with non\-orthogonal correction
* delta coefficients given by: nonOrthDeltaCoeffs
* explicit non\-orthogonal correction

## Usage

The scheme is specified using:

```
snGradSchemes
{
    default         none;
    grad(U)         faceCorrected;
}

```

## Further information

Source code

* [Foam::fv::faceCorrectedSnGrad](https://api.openfoam.com/2606/Foam_fv_faceCorrectedSnGrad.html)
