<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/fixedJump -->

# fixedJump

## Description

The `fixedJump` is a general coupled boundary condition to provide a jump cyclic
condition. The jump is specified as a fixed value field, applied as an offset
to the 'owner' patch.

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
    type            fixedJump;
    jump            <Field<Type>>;

    // Optional entries
    jump0           <Field<Type>>;
    minJump         <Type>;
    relax           <scalar>;

    // Inherited entries
    patchType       <word>;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedJump` | word | yes | \- |
| `jump` | Jump field | Field\<Type\> | yes | \- |
| `jump0` | Old\-time level jump field | Field\<Type\> | no | \- |
| `minJump` | Minimum allowable jump value | Type | no | pTraits\<Type\>::min |
| `relax` | Under\-relaxation factor | scalar | no | \-1 |

The inherited entries are elaborated in:

* [Foam::jumpCyclicFvPatchField](https://api.openfoam.com/2606/Foam_jumpCyclicFvPatchField.html)

* The underlying `patchType` should be set to `cyclic`.

## Further information

Tutorial:

* N/A

Source code:

* [fixedJump](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedJump)

API:

* [Foam::fixedJumpFvPatchField](https://api.openfoam.com/2606/Foam_fixedJumpFvPatchField.html)

**History:** Introduced in version [2\.0\.1](https://www.openfoam.com/news/main-news/openfoam-2.0.1)
