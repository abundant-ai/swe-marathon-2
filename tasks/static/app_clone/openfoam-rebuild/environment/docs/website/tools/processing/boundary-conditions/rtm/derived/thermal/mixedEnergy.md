<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/mixedEnergy -->

# mixedEnergy

## Description

The `mixedEnergy` is a boundary condition that provides
a mixed condition for internal energy.

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
    type            mixedEnergy;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mixedEnergy` | word | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [mixedEnergy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/basic/derivedFvPatchFields/mixedEnergy)

API:

* [Foam::mixedEnergyFvPatchScalarField](https://api.openfoam.com/2606/Foam_mixedEnergyFvPatchScalarField.html)

**History:** Introduced in version [2106](https://www.openfoam.com/news/main-news/openfoam-2106)
