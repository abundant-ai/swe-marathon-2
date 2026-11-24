<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/gradient -->

# Gradient schemes

The gradient of a scalar property ϕ\\phiϕ is represented using the notation:

∇ϕ\=e1∂∂x1ϕ\+e2∂∂x2ϕ\+e3∂∂x3ϕ \\grad \\phi
 \=
 \\vec{e}\_1 \\frac{\\partial}{\\partial x\_1} \\phi
 \+ \\vec{e}\_2 \\frac{\\partial}{\\partial x\_2} \\phi
 \+ \\vec{e}\_3 \\frac{\\partial}{\\partial x\_3} \\phi∇ϕ\=e1​∂x1​∂​ϕ\+e2​∂x2​∂​ϕ\+e3​∂x3​∂​ϕ
where the e\\vec{e}e vectors represent the unit vectors of the 3\-D space.

## Usage

Gradient schemes are specified in the
[fvSchemes](../../../../fundamentals/case-structure/fvschemes.md) file under the `gradSchemes`
sub\-dictionary using the syntax:

```
gradSchemes
{
    default         none;
    grad(p)         <optional limiter> <gradient scheme> <interpolation scheme>;
}

```

## Options

### Gradient schemes

* [Gauss gradient scheme](gradient/rtm/Gauss.md)
* [Least\-squares gradient scheme](gradient/rtm/leastSquares.md)

### Interpolation schemes

* `linear`: cell\-based linear
* `pointLinear`: point\-based linear
* `leastSquares`: Least squares

### Gradient limiters

The limited gradient schemes attempt to preserve the monotonicity condition
by limiting the gradient to ensure that the extrapolated face value is
bounded by the neighbouring cell values.

* `clippedLinear`: limits linear scheme according to a hypothetical cell size
ratio

* [Cell\-limited gradient scheme](gradient/rtm/cellLimited.md)
* [Face\-limited gradient scheme](gradient/rtm/faceLimited.md)
* [Multi\-directional cell\-limited gradient scheme](gradient/rtm/cellMDLimited.md)
* [Multi\-directional face\-limited gradient scheme](gradient/rtm/faceMDLimited.md)

## Example

See [this example](gradient/example.md) to see the
relative performance of the schemes.

## Further information

Source code:

* [gradScheme](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/finiteVolume/gradSchemes/gradScheme)

API:

* [Foam::fv::gradScheme](https://api.openfoam.com/2606/Foam_fv_gradScheme.html)
