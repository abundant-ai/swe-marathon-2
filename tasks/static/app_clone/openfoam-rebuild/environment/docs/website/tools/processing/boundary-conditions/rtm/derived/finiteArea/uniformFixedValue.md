<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/uniformFixedValue -->

# uniformFixedValue

## Description

The `uniformFixedValue` is a boundary condition that provides
a uniform fixed value condition.

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
    type            uniformFixedValue;
    uniformValue <Function1<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformFixedValue` | word | yes | \- |
| `uniformValue` | Uniform value field | Function1\<Type\> | yes | \- |

The inherited entries are elaborated in:

* fixedGradientFaPatchField.H
* Function1\.H

* The `value` entry (optional) is used for the initial values.

```
Otherwise the `uniformValue` is used for the evaluation.
In some cases (eg, coded or expression entries with references to other
fields) this can be problematic and the `value` entry will be needed.

```

## Further information

Tutorial:

* N/A

Source code:

* [uniformFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/uniformFixedValue)

API:

* [Foam::uniformFixedValueFaPatchField](https://api.openfoam.com/2606/Foam_uniformFixedValueFaPatchField.html)

**History:** Introduced in version [v2306](https://www.openfoam.com/news/main-news/openfoam-v2306)
