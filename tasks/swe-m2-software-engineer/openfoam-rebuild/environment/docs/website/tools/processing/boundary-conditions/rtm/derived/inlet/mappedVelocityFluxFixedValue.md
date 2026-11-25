<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/mappedVelocityFluxFixedValue -->

# mappedVelocityFluxFixedValue

## Description

The `mappedVelocityFluxFixedValue` is a velocity boundary condition that maps
the velocity and flux from a neighbour patch to this patch.

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
    type                mappedVelocityFluxFixedValue;

    // Optional entries
    phi                 <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedVelocityFluxFixedValue` | word | yes | \- |
| `phi` | Name of the flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

* This boundary condition can only be applied to patches that are of
the `mappedPolyPatch` type.

## Further information

Tutorial:

* N/A

Source code:

* [mappedVelocityFluxFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedVelocityFluxFixedValue)

API:

* [Foam::mappedVelocityFluxFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_mappedVelocityFluxFixedValueFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
