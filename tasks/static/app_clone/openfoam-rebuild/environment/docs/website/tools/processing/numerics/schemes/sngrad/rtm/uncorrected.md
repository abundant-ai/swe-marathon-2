<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/sngrad/rtm/uncorrected -->

# Uncorrected surface\-normal gradient scheme

∇f⊥Q\=αQP−QN∣d∣ \\snGrad Q
 \=
 \\alpha \\frac{Q\_P \- Q\_N}{\| \\vec{d} \|}∇f⊥​Q\=α∣d∣QP​−QN​​
where

α\=1cos(θ) \\alpha \= \\frac{1}{cos(\\theta)}α\=cos(θ)1​
## Properties

* Central\-difference scheme without non\-orthogonal correction
* Implicit evaluation
* delta coefficients given by: nonOrthDeltaCoeffs

## Usage

The scheme is specified using:

```
snGradSchemes
{
    default         none;
    grad(U)         uncorrected;
}

```

## Further information

Source code

* [Foam::fv::uncorrectedSnGrad](https://api.openfoam.com/2606/Foam_fv_uncorrectedSnGrad.html)
