<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/timeVaryingMappedFixedValue -->

# timeVaryingMappedFixedValue

## Description

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
    type            timeVaryingMappedFixedValue;

    // Optional entries
    setAverage      <bool>;
    perturb         <scalar>;
    points          <word>;
    offset          <Function1<Type>>;
    fieldTable      <word>;
    mapMethod       <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `timeVaryingMappedFixedValue` | word | yes | \- |
| `setAverage` | Use average value | bool | no | false |
| `perturb` | Perturb points for regular geometries | scalar | no | 1e\-5 |
| `points` | Name of points file | word | no | points |
| `fieldTable` | Alternative field name to sample | word | no | this field name |
| `mapMethod` | Type of mapping | word | no | planar |
| `offset` | Offset to mapped values | scalar | no | Zero |

The inherited entries are elaborated in:

* fixedValuePointPatchField.H
* Function1\.H

## Further information

Tutorial:

* N/A

Source code:

* [timeVaryingMappedFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvMotionSolver/pointPatchFields/derived/timeVaryingMappedFixedValue)

API:

* [Foam::timeVaryingMappedFixedValuePointPatchField](https://api.openfoam.com/2606/Foam_timeVaryingMappedFixedValuePointPatchField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
