<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/uniformMixed -->

# uniformMixed

## Description

The `uniformMixed` is a mixed\-type boundary condition that
mix a uniform fixed value and a niform patch\-normal
gradient condition. The term "uniform" is a legacy name since the
prescribed values were previously spatially uniform across that patch.

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
    type                uniformMixed;

    // Optional entries
    uniformValue        <PatchFunction1<Type>>;
    uniformGradient     <PatchFunction1<Type>>;

    // Conditional entries

        // if both 'uniformValue' and 'uniformGradient' entries are set
        uniformValueFraction    <PatchFunction1<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformMixed` | word | yes | \- |
| `uniformValue` | Uniform fixed values | PatchFunction1\<Type\> | no | \- |
| `uniformGradient` | Uniform gradient values | PatchFunction1\<Type\> | no | \- |
| `uniformValueFraction` | Fraction values | PatchFunction1\<Type\> | conditional | \- |

The inherited entries are elaborated in:

* mixedFvPatchField.H
* PatchFunction1\.H

## Further information

Tutorial:

* [TJunctionAverage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/TJunctionAverage)

Source code:

* [uniformMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformMixed)

API:

* [Foam::uniformMixedFvPatchField](https://api.openfoam.com/2606/Foam_uniformMixedFvPatchField.html)

**History:** Introduced in version [v2306](https://www.openfoam.com/news/main-news/openfoam-v2306)
