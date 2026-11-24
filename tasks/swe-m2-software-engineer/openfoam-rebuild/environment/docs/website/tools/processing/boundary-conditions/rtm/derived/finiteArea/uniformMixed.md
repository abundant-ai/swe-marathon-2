<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/uniformMixed -->

# uniformMixed

## Description

The `uniformMixed` is a boundary condition that provides
'mixed' type boundary condition that mix a uniform fixed value and a
uniform patch\-normal gradient condition. The term "uniform" is a legacy name
since the prescribed values were previously spatially uniform across that patch.

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
    type            uniformMixed;

    // Optional entries
    uniformValue    <Function1<Type>>;
    uniformGradient <Function1<Type>>;

    // Conditional entries

        // if 'uniformValue' and 'uniformGradient' entries are set
        uniformValueFraction    <Function1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformMixed` | word | yes | \- |
| `uniformValue` | Uniform fixed values | Function1\<Type\> | no | \- |
| `uniformGradient` | Uniform gradient values | Function1\<Type\> | no | \- |
| `uniformValueFraction` | Fraction values | Function1\<scalar\> | conditional | \- |

The inherited entries are elaborated in:

* fixedGradientFaPatchField.H
* Function1\.H

* This boundary condition allows lazier definitions so that either

```
or both: `uniformValue` and `uniformGradient` must be defined.
If only of these entries is defined, the value fraction is automatically
treated appropriately (ie, 0 with \c uniformGradient and 1 with
`uniformValue`).
If both `uniformValue` and `uniformGradient` are defined,
the `uniformValueFraction` must also be defined.

```

* The `value` entry (optional) is used for the initial values.

```
Otherwise the function(s) are used for the evaluation.
In some cases (eg, coded or expression entries with references to other
fields) this can be problematic and the `value` entry will be needed.

```

## Further information

Tutorial:

* N/A

Source code:

* [uniformMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/uniformMixed)

API:

* [Foam::uniformMixedFaPatchField](https://api.openfoam.com/2606/Foam_uniformMixedFaPatchField.html)

**History:** Introduced in version [v2306](https://www.openfoam.com/news/main-news/openfoam-v2306)
