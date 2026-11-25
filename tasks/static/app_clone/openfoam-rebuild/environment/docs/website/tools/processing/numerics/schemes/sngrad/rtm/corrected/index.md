<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/sngrad/rtm/corrected/ -->

# Corrected surface\-normal gradient scheme

∇f⊥Q\=αQP−QN∣d∣⏟implicit\+(n^−αd^) ∙ (∇Q)f⏟explicit correction \\snGrad Q
 \=
 \\underbrace{\\alpha \\frac{Q\_P \- Q\_N}{\| \\vec{d} \|}}\_{\\mathrm{implicit}}
 \+ \\underbrace{\\left( \\hat{\\vec{n}} \- \\alpha \\hat{\\vec{d}} \\right) \\dprod \\left( \\grad Q \\right)\_f}\_{\\mathrm{explicit\\ correction}}∇f⊥​Q\=implicitα∣d∣QP​−QN​​​​\+explicit correction(n^−αd^)∙(∇Q)f​​​
where

α\=1cos(θ) \\alpha \= \\frac{1}{cos(\\theta)}α\=cos(θ)1​
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
    grad(U)         corrected;
}

```

## Further information

Source code

* [Foam::fv::correctedSnGrad](https://api.openfoam.com/2606/Foam_fv_correctedSnGrad.html)
