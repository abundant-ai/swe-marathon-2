<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/interpolation -->

# Interpolation schemes

Interpolation schemes are used to transform cell\-centre quantities to face
centres. The operation is used in many of the finite volume calculations, e.g.
for the calculation of [gradient](gradient.md),
[divergence](divergence.md), and
[Laplacian](laplacian.md) terms.

## Usage

Interpolation schemes are specified in the
[fvSchemes](../../../../fundamentals/case-structure/fvschemes.md)file under the `interpolationSchemes`
sub\-dictionary using the syntax:

```
interpolationSchemes
{
    default         none;
    <equation term> <interpolation scheme>;
}

```

## Options

A wide variety of interpolation schemes are available, ranging from those that
are based solely on geometry, and others, e.g. convection schemes that are
functions of the local flow.

General

* [Linear](divergence/rtm/linear.md)
* [Point linear](../../../../index.md#schemes-interpolation-point-linear)

Convection

* See [divergence schemes](divergence.md)

## Further information

Source code:

* [surfaceInterpolationScheme](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/surfaceInterpolationScheme)

API:

* [Foam::surfaceInterpolationScheme](https://api.openfoam.com/2606/Foam_surfaceInterpolationScheme.html)
