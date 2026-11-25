<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/fixedNormalSlip -->

# fixedNormalSlip

## Description

The `fixedNormalSlip` is a vector/tensor boundary condition that
sets the patch\-normal component to of the field to the patch\-normal component
of a user specified field. The tangential component is treated as `slip`,
i.e. copied from the internal field.

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
    type                    fixedNormalSlip;
    fixedValue              <vectorField> or <tensorField>;

    // Optional entries
    writeValue              <bool>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedNormalSlip` | word | yes | \- |
| `fixedValue` | User\-defined patch\-normal field | vectorField/tensorField | yes | \- |
| `writeValue` | Write patch values (eg, ParaView) | bool | no | false |

The inherited entries are elaborated in:

* [Foam::transformFvPatchField](https://api.openfoam.com/2606/Foam_transformFvPatchField.html)

## Further information

Tutorial:

* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceDyMFoam/oscillatingBox)

Source code:

* [fixedNormalSlip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedNormalSlip)

API:

* [Foam::fixedNormalSlipFvPatchField](https://api.openfoam.com/2606/Foam_fixedNormalSlipFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
