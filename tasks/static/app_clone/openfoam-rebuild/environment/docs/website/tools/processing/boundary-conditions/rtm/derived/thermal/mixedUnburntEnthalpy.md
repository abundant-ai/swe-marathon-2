<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/mixedUnburntEnthalpy -->

# mixedUnburntEnthalpy

## Description

The `mixedUnburntEnthalpy` is a boundary condition that provides
a mixed condition for unburnt enthalpy.

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
    type            mixedUnburntEnthalpy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mixedUnburntEnthalpy` | word | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [mixedUnburntEnthalpy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/derivedFvPatchFields/mixedUnburntEnthalpy)

API:

* [Foam::mixedUnburntEnthalpyFvPatchScalarField](https://api.openfoam.com/2606/Foam_mixedUnburntEnthalpyFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
