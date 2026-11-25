<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/regionFiniteArea/velocityFilmShell -->

# velocityFilmShell

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
    type            velocityFilmShell;

    // Optional entries
    zeroWallVelocity  <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `velocityFilmShell` | word | yes | \- |
| `zeroWallVelocity` | Flag to enable zero wall velocity | bool | no | true |

The inherited entries are elaborated in:

* mixedFvPatchFields.H
* liquidFilmBase.H

## Further information

Tutorial:

* [pitzDailyWithSprinklers](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/kinematicParcelFoam/pitzDailyWithSprinklers)

Source code:

* [filmShell](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionFaModels/derivedFvPatchFields/filmShell)

API:

* [Foam::velocityFilmShellFvPatchVectorField](https://api.openfoam.com/2606/Foam_velocityFilmShellFvPatchVectorField.html)

**History:** Introduced in version [v2112](https://www.openfoam.com/news/main-news/openfoam-v2112)
