<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutUWallFunction -->

# nutUWallFunction

## Description

The `nutUWallFunction` is boundary condition that provides
a wall function for the turbulent viscosity (i.e. `nut`) based on velocity
(i.e. `U`) for low\- and high\-Reynolds number applications.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            nutUWallFunction;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutUWallFunction` | word | yes | \- |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H
* wallFunctionBlenders.H

* Suffers from non\-exact restart since `correctNut()` (called through
`turbulence->validate`) returns a slightly different value every time
it is called. See `nutUSpaldingWallFunctionFvPatchScalarField.C`.

## Further information

Tutorial:

* [buoyantCavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/buoyantCavity)

Source code:

* [nutUWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutUWallFunction)

API:

* [Foam::nutUWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutUWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
