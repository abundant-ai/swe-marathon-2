<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/surfaceNormalFixedValue -->

# surfaceNormalFixedValue

## Description

The `surfaceNormalFixedValue` is a boundary condition that provides a
surface\-normal vector boundary condition by its magnitude.

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
    type            surfaceNormalFixedValue;
    refValue        <scalarField>;

    // Optional entries
    ramp            <Function1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `surfaceNormalFixedValue` | word | yes | \- |
| `refValue` | Reference value fiueld | scalarField | yes | \- |
| `ramp` | Time\-based ramping | Function1\<scalar\> | no | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* [simpleCar](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/simpleCar)

Source code:

* [surfaceNormalFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/surfaceNormalFixedValue)

API:

* [Foam::surfaceNormalFixedValueFvPatchVectorField](https://api.openfoam.com/2606/Foam_surfaceNormalFixedValueFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
