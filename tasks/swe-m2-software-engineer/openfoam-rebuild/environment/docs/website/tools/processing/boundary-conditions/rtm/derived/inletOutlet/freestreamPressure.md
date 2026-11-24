<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/freestreamPressure -->

# freestreamPressure

## Description

The `freestreamPressure` is a generic boundary condition that provides
a free\-stream condition for pressure. It is an outlet\-inlet condition that
uses the velocity orientation to continuously blend between zero gradient for
normal inlet and fixed value for normal outlet flow.

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
    type            freestreamPressure;
    freestreamValue <scalarField>;

    // Optional entries
    U               <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `freestreamPressure` | word | yes | \- |
| `freestreamValue` | Patch value | scalarField | yes | \- |
| `U` | Name of velocity field | word | no | U |

The inherited entries are elaborated in:

* [Foam::fvPatchField](https://api.openfoam.com/2606/Foam_fvPatchField.html)
* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* [aerofoilNACA0012](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/aerofoilNACA0012)
* [airFoil2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/airFoil2D)

Source code:

* [freestreamPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/freestreamPressure)

API:

* [Foam::freestreamPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_freestreamPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
