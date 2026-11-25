<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/fixedUnburntEnthalpy -->

# fixedUnburntEnthalpy

## Description

The `fixedUnburntEnthalpy` is a boundary condition that provides
a fixed boundary condition for unburnt enthalpy.

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
    type            fixedUnburntEnthalpy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedUnburntEnthalpy` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [fixedUnburntEnthalpy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/derivedFvPatchFields/fixedUnburntEnthalpy)

API:

* [Foam::fixedUnburntEnthalpyFvPatchScalarField](https://api.openfoam.com/2606/Foam_fixedUnburntEnthalpyFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
