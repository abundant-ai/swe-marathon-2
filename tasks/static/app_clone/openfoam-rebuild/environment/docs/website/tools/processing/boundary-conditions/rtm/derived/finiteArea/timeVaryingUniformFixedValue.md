<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/timeVaryingUniformFixedValue -->

# timeVaryingUniformFixedValue

## Description

The `timeVaryingUniformFixedValue` is a boundary condition that provides
a time\-varying form of a uniform fixed value condition for finite area
calculations.

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
    type            timeVaryingUniformFixedValue;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `timeVaryingUniformFixedValue` | word | yes | \- |

The inherited entries are elaborated in:

* faPatchFields.H
* interpolationTable.H

## Further information

Tutorial:

* N/A

Source code:

* [timeVaryingUniformFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/timeVaryingUniformFixedValue)

API:

* [Foam::timeVaryingUniformFixedValueFaPatchField](https://api.openfoam.com/2606/Foam_timeVaryingUniformFixedValueFaPatchField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
