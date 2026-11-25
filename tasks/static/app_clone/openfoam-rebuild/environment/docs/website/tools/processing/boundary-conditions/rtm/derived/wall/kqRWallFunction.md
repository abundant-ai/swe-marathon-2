<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/kqRWallFunction -->

# kqRWallFunction

## Description

The `kqRWallFunction` is boundary condition that provides
a simple wrapper around the zero\-gradient
condition, which can be used for the turbulent kinetic energy (i.e. `k`),
square\-root of turbulent kinetic energy (i.e. `q`) and Reynolds stress
symmetric\-tensor fields (i.e. `R`) for the cases of high Reynolds number
flow using wall functions. It is not a wall\-function condition.

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
    type            kqRWallFunction;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `kqRWallFunction` | word | yes | \- |

The inherited entries are elaborated in:

* zeroGradientFvPatchField.H

## Further information

Tutorial:

* [pitzDaily](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/pitzDaily)

Source code:

* [kqRWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/kqRWallFunctions/kqRWallFunction)

API:

* [Foam::kqRWallFunctionFvPatchField](https://api.openfoam.com/2606/Foam_kqRWallFunctionFvPatchField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
