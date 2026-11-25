<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/gradientUnburntEnthalpy -->

# gradientUnburntEnthalpy

## Description

The `gradientUnburntEnthalpy` is a boundary condition that provides
a gradient boundary condition for unburnt enthalpy.

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
    type            gradientUnburntEnthalpy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `gradientUnburntEnthalpy` | word | yes | \- |

The inherited entries are elaborated in:

* fixedGradientFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [gradientUnburntEnthalpy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/derivedFvPatchFields/gradientUnburntEnthalpy)

API:

* [Foam::gradientUnburntEnthalpyFvPatchScalarField](https://api.openfoam.com/2606/Foam_gradientUnburntEnthalpyFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
