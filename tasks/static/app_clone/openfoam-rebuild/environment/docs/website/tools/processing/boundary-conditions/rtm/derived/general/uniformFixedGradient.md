<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/uniformFixedGradient -->

# uniformFixedGradient

## Description

The `uniformFixedGradient` is a boundary condition that
provides a uniform fixed gradient condition.

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
    type                uniformFixedGradient;
    uniformGradient     <PatchFunction1<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformFixedGradient` | word | yes | \- |
| `uniformGradient` | Uniform gradient values | PatchFunction1\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [fixedGradientFvPatchField.H](fixedGradient.md)
* PatchFunction1\.H

## Further information

Tutorial:

* N/A

Source code:

* [uniformFixedGradient](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformFixedGradient)

API:

* [Foam::uniformFixedGradientFvPatchField](https://api.openfoam.com/2606/Foam_uniformFixedGradientFvPatchField.html)

**History:** Introduced in version [2\.2\.1](https://www.openfoam.com/news/main-news/openfoam-2.2.1)
