<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/scaledFixedValue -->

# scaledFixedValue

## Description

The `scaledFixedValue` is a boundary condition that applies a scalar multiplier
to the value of another boundary condition.

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
    type            scaledFixedValue;
    scale           <PatchFunction1<scalar>>;
    refValue        <fvPatchField<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `scaledFixedValue` | word | yes | \- |
| `scale` | Scalar scale factor | PatchFunction1\<scalar\> | yes | \- |
| `refValue` | Condition to supply the reference value | fvPatchField\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::PatchFunction1](https://api.openfoam.com/2606/Foam_PatchFunction1.html)

## Further information

Tutorial:

* N/A

Source code:

* [scaledFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/scaledFixedValue)

API:

* [Foam::scaledFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_scaledFixedValueFvPatchField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
