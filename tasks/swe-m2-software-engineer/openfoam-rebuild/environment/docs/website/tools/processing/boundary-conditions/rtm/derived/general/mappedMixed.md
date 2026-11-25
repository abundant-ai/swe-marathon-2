<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mappedMixed -->

# mappedMixed

## Description

The `mappedMixed` is a generic boundary condition that maps the value at a
set of cells or patch faces back to the local patch.

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
    type                    mappedMixed;

    // Optional entries
    weightField             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedMixed` | word | yes | \- |
| `weightField` | Name of weight field to sample | word | no | null |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)
* [Foam::mappedPatchFieldBase](https://api.openfoam.com/2606/Foam_mappedPatchFieldBase.html)

## Further information

Tutorial:

* [multiWorld2](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/laplacianFoam/multiWorld2)

Source code:

* [mappedMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedMixed)

API:

* [Foam::mappedMixedFvPatchField](https://api.openfoam.com/2606/Foam_mappedMixedFvPatchField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
