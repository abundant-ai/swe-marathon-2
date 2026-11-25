<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/uniformInterpolatedDisplacement -->

# uniformInterpolatedDisplacement

## Description

The `uniformInterpolatedDisplacement` is a boundary condition that
interpolates a pre\-specified motion which is specified as `pointVectorFields`.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            uniformInterpolatedDisplacement;
    field           <word>;
    interpolationScheme  <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformInterpolatedDisplacement` | word | yes | \- |
| `field` | Name of displacement field | word | yes | \- |
| `interpolationScheme` | Name of interpolation scheme | word | yes | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [uniformInterpolatedDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/uniformInterpolatedDisplacement)

API:

* [Foam::uniformInterpolatedDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_uniformInterpolatedDisplacementPointPatchVectorField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
