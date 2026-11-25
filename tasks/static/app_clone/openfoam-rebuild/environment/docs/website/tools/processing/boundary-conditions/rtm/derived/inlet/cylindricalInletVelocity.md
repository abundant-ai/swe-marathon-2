<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/cylindricalInletVelocity -->

# cylindricalInletVelocity

## Description

The `cylindricalInletVelocity` is a velocity inlet boundary condition to model
inlet velocity in cylindrical coordinates using a central axis, central point,
revolutions per minute (rpm), axial and radial velocity magnitudes.

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
    type            cylindricalInletVelocity;
    origin          <vector>;
    axis            <vector>;
    axialVelocity   <Function1<scalar>>;
    radialVelocity  <Function1<scalar>>;
    rpm             <Function1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `cylindricalInletVelocity` | word | yes | \- |
| `origin` | Origin of the rotation | vector | yes | \- |
| `axis` | Axis of the rotation | vector | yes | \- |
| `axialVelocity` | Axial speed | Function1\<scalar\> | yes | \- |
| `radiaVelocity` | Radial speed | Function1\<scalar\> | yes | \- |
| `rpm` | Revolutions per minute | Function1\<scalar\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* [annularCombustorTurbine](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/XiDyMFoam/annularCombustorTurbine)

Source code:

* [cylindricalInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/cylindricalInletVelocity)

API:

* [Foam::cylindricalInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_cylindricalInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
