<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutkRoughWallFunction -->

# nutkRoughWallFunction

## Description

The `nutkRoughWallFunction` is boundary condition that provides
a wall\-function for the turbulent viscosity (i.e. `nut`) when using wall
functions for rough walls, based on the turbulent kinetic energy (i.e. `k`).
The condition manipulates the wall roughness parameter (i.e. `E`) to account
for roughness effects.

Parameter ranges:

* Roughness height (i.e. `Ks`)\= sand\-grain roughness (0 for smooth walls)
* Roughness constant (i.e. `Cs`) \= 0\.5\-1\.0\.

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
    type            nutkRoughWallFunction;
    Ks              <scalarField>;
    Cs              <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutkRoughWallFunction` | word | yes | \- |
| `Ks` | Sand\-grain roughness height | scalarField | yes | \- |
| `Cs` | Roughness constant | scalarField | yes | \- |

The inherited entries are elaborated in:

* nutkWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* [damBreakWithObstacle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/damBreakWithObstacle)

Source code:

* [nutkRoughWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutkRoughWallFunction)

API:

* [Foam::nutkRoughWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutkRoughWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
