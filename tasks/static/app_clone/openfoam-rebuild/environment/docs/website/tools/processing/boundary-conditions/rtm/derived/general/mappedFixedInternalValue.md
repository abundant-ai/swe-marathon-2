<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mappedFixedInternalValue -->

# mappedFixedInternalValue

## Description

The `mappedFixedInternalValue` is a generic boundary condition that maps the
boundary and internal values of a neighbour patch field to the boundary and
internal values of the local patch.

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
    type                    mappedFixedInternalValue;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedFixedInternalValue` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::mappedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedValueFvPatchField.html)

* This boundary condition can only be applied to patches that are of
the `mappedPolyPatch` type.

## Further information

Tutorial:

* N/A

Source code:

* [mappedFixedInternalValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedFixedInternalValue)

API:

* [Foam::mappedFixedInternalValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedInternalValueFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
