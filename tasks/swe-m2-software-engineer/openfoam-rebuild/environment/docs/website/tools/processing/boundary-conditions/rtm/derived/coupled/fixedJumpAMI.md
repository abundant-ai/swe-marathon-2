<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/fixedJumpAMI -->

# fixedJumpAMI

## Description

The `fixedJumpAMI` is a general coupled boundary condition to provide a jump
condition across non\-conformal cyclic patch pairs (employing `AMI`). The jump is
specified as a fixed value field, applied as an offset to the 'owner' patch.

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
    type            fixedJumpAMI;
    jump            <Field<Type>>;

    // Inherited entries
    patchType       <word>;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedJumpAMI` | word | yes | \- |
| `jump` | Jump field | Field\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::jumpCyclicAMIFvPatchField](https://api.openfoam.com/2606/Foam_jumpCyclicAMIFvPatchField.html)

* The underlying `patchType` should be set to `cyclicAMI`.

## Further information

Tutorial:

* N/A

Source code:

* [fixedJumpAMI](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedJumpAMI)

API:

* [Foam::fixedJumpAMIFvPatchField](https://api.openfoam.com/2606/Foam_fixedJumpAMIFvPatchField.html)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
