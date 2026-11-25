<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutURoughWallFunction -->

# nutURoughWallFunction

## Description

The `nutURoughWallFunction` is boundary condition that provides
a wall function on the turbulent viscosity (i.e. `nut`) based on velocity
(i.e. `U`) for low\- and high\-Reynolds number applications for rough walls.

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
    type                nutURoughWallFunction;
    roughnessHeight     <scalar>;
    roughnessConstant   <scalar>;
    roughnessFactor     <scalar>;

    // Optional entries
    maxIter             <label>;
    tolerance           <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutURoughWallFunction` | word | yes | \- |
| `roughnessHeight` | Roughness height | scalar | yes | \- |
| `roughnessConstant` | Roughness constant | scalar | yes | \- |
| `roughnessFactor` | Scaling factor | scalar | yes | \- |
| `maxIter` | Number of Newton\-Raphson iterations | label | no | 10 |
| `tolerance` | Convergence tolerance | scalar | no | 0\.0001 |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H

* Suffers from non\-exact restart since `correctNut()` (called through
`turbulence->validate`) returns a slightly different value every time
it is called. See `nutUSpaldingWallFunctionFvPatchScalarField.C`.

## Further information

Tutorial:

* N/A

Source code:

* [nutURoughWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutURoughWallFunction)

API:

* [Foam::nutURoughWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutURoughWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
