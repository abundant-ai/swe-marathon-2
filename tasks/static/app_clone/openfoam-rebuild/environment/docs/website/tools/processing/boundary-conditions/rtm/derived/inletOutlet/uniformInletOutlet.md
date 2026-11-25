<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/uniformInletOutlet -->

# uniformInletOutlet

## Description

The `uniformInletOutlet` is a boundary condition that provides
a variant of the `inletOutlet` boundary condition with uniform `inletValue`.

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
    type            uniformInletOutlet;
    uniformInletValue  <Function1<Type>>;

    // Optional entries
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformInletOutlet` | word | yes | \- |
| `uniformInletValue` | Uniform inlet value field | Function1\<Type\> | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* mixedFvPatchField.H
* Function1\.H

## Further information

Tutorial:

* N/A

Source code:

* [uniformInletOutlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformInletOutlet)

API:

* [Foam::uniformInletOutletFvPatchField](https://api.openfoam.com/2606/Foam_uniformInletOutletFvPatchField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
