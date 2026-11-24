<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/freestream -->

# freestream

## Description

The `freestream` is a generic boundary condition that provides
a free\-stream condition. It is a `mixed` condition derived from the
`inletOutlet` condition, whereby the mode of operation switches between
fixed (free stream) value and zero gradient based on the sign of the flux.

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
    type            freestream;

    // Conditional entries

        // Option-1
        freestreamValue        <Field<Type>>;

        // Option-2
        freestreamBC           <fvPatchField<Type>>;

    // Optional entries
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `freestream` | word | yes | \- |
| `freestreamValue` | Patch value | Field\<Type\> | choice | \- |
| `freestreamBC` | Separate boundary condition | fvPatchField\<Type\> | choice | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::inletOutletFvPatchField](https://api.openfoam.com/2606/Foam_inletOutletFvPatchField.html)

## Further information

Tutorial:

* [aerofoilNACA0012](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/aerofoilNACA0012)
* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)

Source code:

* [freestream](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/freestream)

API:

* [Foam::freestreamFvPatchField](https://api.openfoam.com/2606/Foam_freestreamFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
