<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/slip -->

# slip

## Description

The `slip` is boundary condition that provides the slip constraint.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
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

* [Foam::basicSymmetryFvPatchField](https://api.openfoam.com/2606/Foam_basicSymmetryFvPatchField.html)

## Further information

Tutorial:

* [sloshing2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/sloshing2D)

Source code:

* [slip](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/slip)

API:

* [Foam::slipFvPatchField](https://api.openfoam.com/2606/Foam_slipFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
