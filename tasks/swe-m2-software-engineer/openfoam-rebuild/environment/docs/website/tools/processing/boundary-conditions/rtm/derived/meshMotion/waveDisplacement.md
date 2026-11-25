<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/waveDisplacement -->

# waveDisplacement

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
    type            waveDisplacement;
    amplitude       <vector>;
    omega           <scalar>;

    // Optional entries
    waveNumber      <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waveDisplacement` | word | yes | \- |
| `amplitude` | Amplitude | word | yes | \- |
| `omega` | Omega | word | yes | \- |
| `waveNumber` | Wave number | word | yes | \- |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [waveDisplacement](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/waveDisplacement)

API:

* [Foam::waveDisplacementPointPatchVectorField](https://api.openfoam.com/2606/Foam_waveDisplacementPointPatchVectorField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
