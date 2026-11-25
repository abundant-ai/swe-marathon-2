<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/rtm/filteredLinear2 -->

# Filtered Linear (2\) divergence scheme

## Properties

* Second order
* Unbounded
* Attempts to limit the unboundedness of the [linear](linear.md) scheme

## Usage

The scheme is specified using:

```
divSchemes
{
    default         none;
    div(phi,U)      Gauss filteredLinear2 <k> <l>;
}

```

Where the coefficients

* `k`: Scales the rate at which the correction is applied
	+ 0 : linear
	+ 1 : fully limited
* `l`: Maximum allowed overshoot/undershoot relative to the difference across
the face.
	+ 0 : no overshoot/undershoot
	+ 1 : overshoot/undershoot equal to the difference across the face

## Further information

Source code:

* [filteredLinear2](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/interpolation/surfaceInterpolation/limitedSchemes/filteredLinear2)

API:

* [Foam::filteredLinear2Limiter](https://api.openfoam.com/2606/Foam_filteredLinear2Limiter.html)
