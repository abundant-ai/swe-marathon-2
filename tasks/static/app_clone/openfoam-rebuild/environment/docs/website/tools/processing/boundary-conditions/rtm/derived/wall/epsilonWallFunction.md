<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/epsilonWallFunction -->

# epsilonWallFunction

## Description

The `epsilonWallFunction` is boundary condition that provides
wall functions for the turbulent kinetic energy dissipation rate
(i.e. `epsilon`) and the turbulent kinetic energy production contribution
(i.e. `G`) for low\- and high\-Reynolds number simulations.

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
    type            epsilonWallFunction;

    // Optional entries
    lowReCorrection  <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `epsilonWallFunction` | word | yes | \- |
| `lowReCorrection` | Flag: apply low\-Re correction | bool | no | false |

The inherited entries are elaborated in:

* wallFunctionCoefficients.H
* wallFunctionBlenders.H

## Further information

Tutorial:

* [planeChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/turbulenceModels/planeChannel)

Source code:

* [epsilonWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/epsilonWallFunctions/epsilonWallFunction)

API:

* [Foam::epsilonWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_epsilonWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
