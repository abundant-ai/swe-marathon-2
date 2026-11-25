<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/rtm/CoBlended -->

# Courant number blended divergence scheme

## Properties

* Blends two schemes based on the local face\-based Courant number

## Usage

The scheme is specified using:

```
divSchemes
{
    default         none;
    div(phi,U)      Gauss CoBlended <co1> <scheme1> <co2> <scheme2>;
}

```

Where

* Co \< `co1` : `scheme1`
* Co \> `co2` : `scheme2`
* `co1` \< Co \< `co2` : linear blend between `<scheme1>` and `<scheme2>`

Note: If a scheme with optional entries (such as the `DEShybrid` scheme) is used
as `<scheme1>` within `CoBlended`, the user must provide all entries, both
mandatory and optional. Failing to do so will result in a fatal error.

## Further information

Source code:

* [CoBlended](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/schemes/CoBlended)

API:

* [Foam::CoBlended](https://api.openfoam.com/2606/Foam_CoBlended.html)
