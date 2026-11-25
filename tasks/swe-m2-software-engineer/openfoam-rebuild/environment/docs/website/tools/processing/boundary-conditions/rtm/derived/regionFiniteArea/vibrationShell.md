<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/regionFiniteArea/vibrationShell -->

# vibrationShell

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
    type            vibrationShell;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `vibrationShell` | word | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H
* vibrationShellModel.H

## Further information

Tutorial:

* [obliqueAirJet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/acousticFoam/obliqueAirJet)

Source code:

* [vibrationShell](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionFaModels/derivedFvPatchFields/vibrationShell)

API:

* [Foam::vibrationShellFvPatchScalarField](https://api.openfoam.com/2606/Foam_vibrationShellFvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
