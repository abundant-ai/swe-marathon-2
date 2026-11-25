<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/fixedInternalValue -->

# fixedInternalValue

## Description

The `fixedInternalValue` is a general boundary condition to
provide a mechanism to set boundary (cell) values directly into a matrix,
i.e. to set a constraint condition. Default behaviour is to act as a zero
gradient condition.

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
    type                    fixedInternalValue;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedInternalValue` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::zeroGradientFvPatchField](https://api.openfoam.com/2606/Foam_zeroGradientFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [fixedInternalValueFvPatchField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedInternalValueFvPatchField)

API:

* [Foam::fixedInternalValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedInternalValueFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
