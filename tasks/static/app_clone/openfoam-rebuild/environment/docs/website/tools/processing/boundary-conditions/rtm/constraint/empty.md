<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/constraint/empty -->

# Empty

## Properties

Applied pairs in reduced dimension cases to represent the directions that are
not solved, i.e.:

* 1\-D: sides of the 1\-D stack of cells
* 2\-D: front and back planes

## Usage

The condition requires entries in both the `boundary` and field files. Mesh
`boundary` file:

```
<patchName>
{
    type            empty;
    ...
}

```

Field file:

```
<patchName>
{
    type            empty;
}

```

## Details

* Separation between `empty` patch pairs must be
	+ a single layer of cells
	+ cells should be uniform thickness in the non\-solved direction, and
	+ points should appear collocated when viewed in the patch normal direction
* Particles will be snapped to the mid\-plane between pairs of `empty` patches

## Further information

Source code:

* [empty](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/constraint/empty)

API:

* [Foam::emptyFvPatchField](https://api.openfoam.com/2606/Foam_emptyFvPatchField.html)
