<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/freestreamVelocity -->

# freestreamVelocity

## Description

The `freestreamVelocity` is a generic boundary condition that provides
a free\-stream condition for velocity. It is an inlet\-outlet condition that uses
the velocity orientation to continuously blend between fixed value for normal
inlet and zero gradient for normal outlet flow.

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
    type            freestreamVelocity;
    freestreamValue <vectorField>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `freestreamVelocity` | word | yes | \- |
| `freestreamValue` | Patch value | vectorField | yes | \- |

The inherited entries are elaborated in:

* [Foam::fvPatchField](https://api.openfoam.com/2606/Foam_fvPatchField.html)
* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* [aerofoilNACA0012](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/aerofoilNACA0012)
* [airFoil2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/airFoil2D)

Source code:

* [freestreamVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/freestreamVelocity)

API:

* [Foam::freestreamVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_freestreamVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
