<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/solidBodyMotionDisplacement -->

# solidBodyMotionDisplacement

## Description

The `solidBodyMotionDisplacement` is a boundary condition that
enables the specification of a fixed value boundary condition using the
solid body motion functions for point displacements.

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
    type            solidBodyMotionDisplacement;
    solidBodyMotionFunction    <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `solidBodyMotionDisplacement` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchFields.H
* solidBodyMotionFunction.H

## Further information

Tutorial:

* [box2D\_moveDynamicMesh](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/moveDynamicMesh/relativeMotion/box2D_moveDynamicMesh)

Source code:

* [solidBodyMotionDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/dynamicMesh/motionSolvers/displacement/solidBody/pointPatchFields/derived/solidBodyMotionDisplacement)

API:

* [Foam::solidBodyMotionDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_solidBodyMotionDisplacementPointPatchVectorField.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
