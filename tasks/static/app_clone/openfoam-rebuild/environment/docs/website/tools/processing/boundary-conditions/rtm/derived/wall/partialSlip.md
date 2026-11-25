<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/partialSlip -->

# partialSlip

## Description

The `partialSlip` is a velocity boundary condition that determines
the amount of slip is controlled by a user\-supplied field.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            partialSlip;
    valueFraction   <Field>;

    // Optional entries
    refValue        <Field>;
    writeValue      <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `partialSlip` | word | yes | \- |
| `valueFraction` | Fraction of refValue used for boundary \[0\-1] | Field | yes | \- |
| `refValue` | Reference value at zero slip | Field | no | Zero |
| `writeValue` | Flag to output patch values (e.g. for ParaView) | bool | no | false |

The inherited entries are elaborated in:

* [Foam::transformFvPatchField](https://api.openfoam.com/2606/Foam_transformFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [partialSlip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/partialSlip)

API:

* [Foam::partialSlipFvPatchField](https://api.openfoam.com/2606/Foam_partialSlipFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
