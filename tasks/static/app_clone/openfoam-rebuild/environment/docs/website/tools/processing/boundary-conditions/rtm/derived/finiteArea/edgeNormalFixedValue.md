<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/edgeNormalFixedValue -->

# edgeNormalFixedValue

## Description

The `edgeNormalFixedValue` is a boundary condition that provides
an edge normal fixed value vector field for finite area calculations.

This condition describes a surface normal vector boundary condition by its
magnitude.

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
    type            edgeNormalFixedValue;
    refValue        <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `edgeNormalFixedValue` | word | yes | \- |
| `refValue` | Edge\-normal velocity field | scalarField | yes | \- |

The inherited entries are elaborated in:

* fixedValueFaPatchFields.H

* The value is positive for outward\-pointing vectors.

## Further information

Tutorial:

* N/A

Source code:

* [edgeNormalFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/edgeNormalFixedValue)

API:

* [Foam::edgeNormalFixedValueFaPatchVectorField](https://api.openfoam.com/2606/Foam_edgeNormalFixedValueFaPatchVectorField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
