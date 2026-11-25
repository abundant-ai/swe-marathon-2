<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient/rtm/Gauss -->

# Gauss gradient scheme

## Properties

The cell gradient is calculated using [Gauss'](../../gauss-theorem.md) theorem:

∫V(∇ ∙ u)dV\=∮S(n ∙ u)dS \\int\_V \\left( \\div \\u \\right) dV
 \= \\oint\_S \\left( \\vec{n} \\dprod \\u \\right) dS∫V​(∇∙u)dV\=∮S​(n∙u)dS
## Usage

The scheme is specified using:

```
gradSchemes
{
    default         none;
    grad(U)         Gauss <interpolation scheme>;
}

```

## Further information

Source code

* [Foam::fv::gaussGrad](https://api.openfoam.com/2606/Foam_fv_gaussGrad.html)
