<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/rtm/LUST -->

# LUST divergence scheme

## Properties

* \<B\>L\</B\>inear\-\<B\>U\</B\>pwind \<B\>S\</B\>tabilised \<B\>T\</B\>ransport
* Fixed blended scheme with 0\.25 [linearUpwind](linearUpwind.md)
and 0\.75 [linear](linear.md) weights
* Unbounded

## Usage

The scheme is specified using:

```
divSchemes
{
    default         none;
    div(phi,U)      Gauss LUST <grad-scheme>;
}

```

Where `<grad-scheme>` is a gradient scheme, e.g.

```
divSchemes
{
    default         none;
    div(phi,U)      Gauss LUST grad(U);
}

```

## Further information

Source code:

* [LUST](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/schemes/LUST)

API:

* [Foam::LUST](https://api.openfoam.com/2606/Foam_LUST.html)
