<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutUTabulatedWallFunction -->

# nutUTabulatedWallFunction

## Description

The `nutUTabulatedWallFunction` is boundary condition that provides
a wall constraint on the turbulent viscosity (i.e. `nut`) based on velocity
(i.e. `U`), for low\- and high\-Reynolds number applications.

As input, the user specifies a look\-up table of `u+` as a function of
near\-wall Reynolds number.

The table should be located in the `$FOAM_CASE/constant` directory.

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
    type            nutUTabulatedWallFunction;
    uPlusTable      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutUTabulatedWallFunction` | word | yes | \- |
| `uPlusTable` | u\+ as a function of Re table name | word | yes | \- |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H
* uniformInterpolationTable.H

* The tables are not registered since the same table object may be used for
more than one patch.

## Further information

Tutorial:

* N/A

Source code:

* [nutUTabulatedWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutUTabulatedWallFunction)

API:

* [Foam::nutUTabulatedWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutUTabulatedWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
