<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/uniformNormalFixedValue -->

# uniformNormalFixedValue

## Description

The `uniformNormalFixedValue` is a boundary condition that
provides a uniform surface\-normal vector condition by its magnitude.

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
    type            uniformNormalFixedValue;
    uniformValue    <PatchFunction1<Type>>;

    // Optional entries
    ramp            <Function1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformNormalFixedValue` | word | yes | \- |
| `uniformValue` | Patch field values | PatchFunction1\<Type\> | yes | \- |
| `ramp` | Time\-variant ramp | Function1\<scalar\> | no | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* PatchFunction1\.H
* Function1\.H

* Sign conventions:
	+ the value is positive for outward\-pointing vectors

## Further information

Tutorial:

* [windshieldCondensation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/windshieldCondensation)

Source code:

* [uniformNormalFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformNormalFixedValue)

API:

* [Foam::uniformNormalFixedValueFvPatchVectorField](https://api.openfoam.com/2606/Foam_uniformNormalFixedValueFvPatchVectorField.html)

**History:** Introduced in version [v1912](https://www.openfoam.com/news/main-news/openfoam-v1912)
