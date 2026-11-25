<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/surfaceDisplacement -->

# surfaceDisplacement

## Description

The `surfaceDisplacement` is a boundary condition that provides displacement
fixed by projection onto triSurface. Use in a `displacementMotionSolver`
as a boundary condition on a `pointDisplacement` field.

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
    type            surfaceDisplacement;
    velocity        <vector>;
    geometry        <dict>;
    projectMode     <word>;
    projectDirection  <vector>;

    // Optional entries
    wedgePlane      <label>;
    frozenPointsZone  <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `surfaceDisplacement` | word | yes | \- |
| `velocity` | Maximum velocity | vector | yes | \- |
| `geometry` | Dictionary with `searchableSurfaces`. (usually `triSurfaceMeshes` in `constant/triSurface`) | word | yes | \- |
| `projectMode` | Projection mode | word | yes | \- |
| `projectDirection` | Projection direction | vector | yes | \- |
| `wedgePlane` | \-1 or component to knock out of intersection normal | label | no | \-1 |
| `frozenPointsZone` | Empty or name of `pointZone` containing points that do not move | word | no | null |

Options for the `projectMode` entry:

| Property | Description |
| --- | --- |
| `NEAREST` | Nearest |
| `POINTNORMAL` | Intersection with point normal |
| `FIXEDNORMAL` | Intersection with fixed vector |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

* This displacement is then clipped with the specified velocity\*deltaT.
* Optionally (intersection only) removes a component (`wedgePlane`) to
stay in 2D.

## Further information

Tutorial:

* [SnakeRiverCanyon](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/moveDynamicMesh/SnakeRiverCanyon)

Source code:

* [surfaceDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/surfaceDisplacement)

API:

* [Foam::surfaceDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_surfaceDisplacementPointPatchVectorField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
