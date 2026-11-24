<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutkWallFunction -->

# nutkWallFunction

## Description

The `nutkWallFunction` is boundary condition that provides
a wall function for the turbulent viscosity (i.e. `nut`) based
on the turbulent kinetic energy, (i.e. `k`) for for low\- and high\-Reynolds
number applications.

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
    type            nutkWallFunction;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutkWallFunction` | word | yes | \- |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H
* wallFunctionBlenders.H

## Further information

Tutorial:

* [pipeCyclic](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/pipeCyclic)

Source code:

* [nutkWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutkWallFunction)

API:

* [Foam::nutkWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutkWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
