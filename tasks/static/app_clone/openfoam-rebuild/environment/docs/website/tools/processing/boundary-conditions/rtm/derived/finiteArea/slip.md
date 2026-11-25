<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/slip -->

# slip

## Description

The `slip` is a boundary condition that provides the slip constraint.

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
    type            slip;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `slip` | word | yes | \- |

The inherited entries are elaborated in:

* basicSymmetryFaPatchField.H

## Further information

Tutorial:

* [cylinder](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/finiteArea/liquidFilmFoam/cylinder)

Source code:

* [slip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/slip)

API:

* [Foam::slipFaPatchField](https://api.openfoam.com/2606/Foam_slipFaPatchField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
