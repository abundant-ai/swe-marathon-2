<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/timeVaryingMappedFixedValue -->

# timeVaryingMappedFixedValue

## Description

The `timeVaryingMappedFixedValue` is a boundary condition
that interpolates the values from a set of supplied points in space and time.

Supplied data should be specified in `constant/boundaryData/\<patchname\>/`

* `points` : pointField of locations
* `\<time\>/\<field\>` : field of values at time `\<time\>`

The default mode of operation (`mapMethod` \= `planar`) is to project
the points onto a plane (constructed from the first three points) and
construct a 2D triangulation and finds for the face centres the triangle it
is in and the weights to the 3 vertices.

The optional mapMethod nearest will avoid all projection and triangulation
and just use the value at the nearest vertex.

Values are interpolated linearly between times.

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
    uniformValue    <PatchFunction1Types::MappedFile<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `timeVaryingMappedFixedValue` | word | yes | \- |
| `uniformValue` | Data | PatchFunction1Types::MappedFile\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::PatchFunction1Types::MappedFile](https://api.openfoam.com/2606/Foam_PatchFunction1Types_MappedFile.html)

## Further information

Tutorial:

* [pitzDailyExptInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/pitzDailyExptInlet)

Source code:

* [timeVaryingMappedFixedValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/timeVaryingMappedFixedValue)

API:

* [Foam::timeVaryingMappedFixedValueFvPatchField](https://api.openfoam.com/2606/Foam_timeVaryingMappedFixedValueFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
