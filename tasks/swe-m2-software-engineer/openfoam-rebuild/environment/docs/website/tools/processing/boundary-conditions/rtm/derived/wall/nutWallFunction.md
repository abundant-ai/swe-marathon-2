<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutWallFunction -->

# nutWallFunction

## Description

The `nutWallFunction` is an abstract base class that
hosts y\+y^\+y\+ calculation methods and common functions for
`nut` wall\-function boundary conditions.

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
    // Optional entries
    U               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `U` | Name of velocity field | word | no | U |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* wallFunctionCoefficients.H

## Further information

Tutorial:

* N/A

Source code:

* [nutWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutWallFunction)

API:

* [Foam::nutWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
