<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mappedFixedValue -->

# mappedFixedValue

## Description

The `mappedFixedValue` is a generic boundary condition that maps the value
at a set of cells or patch faces back to the local patch.

The sample mode is set by the underlying mapping engine, provided by the
`mappedPatchBase` class.

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
    type                    mappedFixedValue;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedFixedValue` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::mappedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedValueFvPatchField.html)

* It is not possible to sample internal faces since volume fields are not
defined on faces.

## Further information

Tutorial:

* N/A

Source code:

* [mappedFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedFixedValue)

API:

* [Foam::mappedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedFixedValueFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
