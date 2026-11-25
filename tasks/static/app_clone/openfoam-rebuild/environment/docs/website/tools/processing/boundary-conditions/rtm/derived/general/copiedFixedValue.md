<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/copiedFixedValue -->

# copiedFixedValue

## Description

The `copiedFixedValue` is a generic boundary condition that
copies the boundary values from a user specified field.

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
    type            copiedFixedValue;
    sourceFieldName     <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `copiedFixedValue` | word | yes | \- |
| `sourceFieldName` | Name of the source field | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [wallBoiling1D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/wallBoiling1D)

Source code:

* [copiedFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/copiedFixedValue)

API:

* [Foam::copiedFixedValueFvPatchScalarField](https://api.openfoam.com/2606/Foam_copiedFixedValueFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
