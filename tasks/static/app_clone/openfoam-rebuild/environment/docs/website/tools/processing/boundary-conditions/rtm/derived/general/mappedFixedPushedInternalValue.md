<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mappedFixedPushedInternalValue -->

# mappedFixedPushedInternalValue

## Description

The `mappedFixedPushedInternalValue` is a generic boundary condition that maps
the boundary values of a neighbour patch field to the boundary and internal
cell values of the local patch.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            mappedPatch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                    mappedFixedPushedInternalValue;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedFixedPushedInternalValue` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::mappedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedValueFvPatchField.html)

* This boundary condition can only be applied to patches that are of
the `mappedPolyPatch` type.

## Further information

Tutorial:

* N/A

Source code:

* [mappedFixedPushedInternalValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedFixedPushedInternalValue)

API:

* [Foam::mappedFixedPushedInternalValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedPushedInternalValueFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
