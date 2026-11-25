<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/uniformFixedValue -->

# uniformFixedValue

## Description

The `uniformFixedValue` is a boundary condition that
provides a uniform fixed value condition.

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
    type                uniformFixedValue;
    uniformValue        <PatchFunction1<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformFixedValue` | word | yes | \- |
| `uniformValue` | Uniform fixed values | PatchFunction1\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [fixedValueFvPatchField.H](fixedValue.md)
* PatchFunction1\.H

## Further information

Tutorial:

* [turbineSiting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbineSiting)

Source code:

* [uniformFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformFixedValue)

API:

* [Foam::uniformFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_uniformFixedValueFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
