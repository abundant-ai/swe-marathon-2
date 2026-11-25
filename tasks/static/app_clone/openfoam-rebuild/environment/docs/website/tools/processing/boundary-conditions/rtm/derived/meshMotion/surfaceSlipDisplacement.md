<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/surfaceSlipDisplacement -->

# surfaceSlipDisplacement

## Description

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
    type            surfaceSlipDisplacement;
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
| `type` | Type name: `surfaceSlipDisplacement` | word | yes | \- |
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

* pointPatchFields.H

## Further information

Tutorial:

* [SnakeRiverCanyon](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/moveDynamicMesh/SnakeRiverCanyon)

Source code:

* [surfaceSlipDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/surfaceSlipDisplacement)

API:

* [Foam::surfaceSlipDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_surfaceSlipDisplacementPointPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
