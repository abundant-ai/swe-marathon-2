<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/fixedEnergy -->

# fixedEnergy

## Description

The `fixedEnergy` is a boundary condition that provides
a fixed condition for internal energy.

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
    type            fixedEnergy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedEnergy` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [fixedEnergy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/basic/derivedFvPatchFields/fixedEnergy)

API:

* [Foam::fixedEnergyFvPatchScalarField](https://api.openfoam.com/2606/Foam_fixedEnergyFvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
