<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/constraint/symmetryPlane/ -->

# Symmetry plane

## Properties

Applied to planar patches to represent a symmetry condition.

## Usage

The condition requires entries in both the `boundary` and field files. Mesh
`boundary` file:

```
<patchName>
{
    type            symmetryPlane;
    ...
}

```

Field file:

```
<patchName>
{
    type            symmetryPlane;
}

```

## Further information

Source code:

* [Foam::symmetryPlaneFvPatchField](https://api.openfoam.com/2606/Foam_symmetryPlaneFvPatchField.html)
