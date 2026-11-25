<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/fixedNormalSlip -->

# fixedNormalSlip

## Description

The `fixedNormalSlip` is a generic boundary condition that sets the patch\-normal
component to the field to a user specified field. The tangential component is
treated as `slip`.

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
    type                    fixedNormalSlip;
    fixedValue              <Type>;

    // Optional entries
    writeValue              <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedNormalSlip` | word | yes | \- |
| `fixedValue` | User\-defined value for the normal component | Type | yes | \- |
| `writeValue` | Output patch values (eg, ParaView) | bool | no | false |

The inherited entries are elaborated in:

* [Foam::transformFvPatchField](https://api.openfoam.com/2606/Foam_transformFvPatchField.html)

## Further information

Tutorial:

* [SnakeRiverCanyon](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/moveDynamicMesh/SnakeRiverCanyon)
* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceDyMFoam/oscillatingBox)

Source code:

* [fixedNormalSlip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedNormalSlip)

API:

* [Foam::fixedNormalSlipFvPatchField](https://api.openfoam.com/2606/Foam_fixedNormalSlipFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
