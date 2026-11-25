<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/uniformJumpAMI -->

# uniformJumpAMI

## Description

The `uniformJumpAMI` is a general coupled boundary condition that
provides a jump condition, using the `cyclicAMI` condition as a base.
The jump is specified as a time\-varying uniform value across the patch.

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
    type            uniformJumpAMI;
    jumpTable       <Function1<Type>>;

    // Inherited entries
    patchType       cyclicAMI;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformJumpAMI` | word | yes | \- |
| `jumpTable` | Jump values | Function1\<Type\> | yes | \- |

The inherited entries are elaborated in:

* fixedJumpFvPatchField.H
* Function1\.H

* The underlying `patchType` should be set to `cyclicAMI`.

## Further information

Tutorial:

* N/A

Source code:

* [uniformJumpAMI](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformJumpAMI)

API:

* [Foam::uniformJumpAMIFvPatchField](https://api.openfoam.com/2606/Foam_uniformJumpAMIFvPatchField.html)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
