<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/oscillatingDisplacement -->

# oscillatingDisplacement

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
    type            oscillatingDisplacement;
    amplitude       <vector>;
    omega           <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `oscillatingDisplacement` | word | yes | \- |
| `amplitude` | Oscillation amplitude | scalar | yes | \- |
| `omega` | Rotation speed | scalar | yes | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceDyMFoam/oscillatingBox)

Source code:

* [oscillatingDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/oscillatingDisplacement)

API:

* [Foam::oscillatingDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_oscillatingDisplacementPointPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
