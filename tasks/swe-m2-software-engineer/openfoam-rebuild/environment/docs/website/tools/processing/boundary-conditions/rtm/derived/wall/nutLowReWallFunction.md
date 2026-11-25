<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutLowReWallFunction -->

# nutLowReWallFunction

## Description

The `nutLowReWallFunction` is boundary condition that provides
a simple wrapper around a zero
fixed\-value condition for the turbulent viscosity (i.e. `nut`)
for low\-Reynolds number applications. It sets `nut` to zero,
and provides an access function to calculate y\+.

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
    type            nutLowReWallFunction;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutLowReWallFunction` | word | yes | \- |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* [ellipsekkLOmega](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/ellipsekkLOmega)

Source code:

* [nutLowReWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutLowReWallFunction)

API:

* [Foam::nutLowReWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutLowReWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
