<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/constraint/wedge -->

# Wedge

## Properties

Applied in pairs to 2\-D rotationally symmetric cases to represent planes in
the swirl direction.

## Usage

The condition requires entries in both the `boundary` and field files. Mesh
`boundary` file:

```
<patchName>
{
    type            wedge;
    ...
}

```

Field file:

```
<patchName>
{
    type            wedge;
}

```

## Details

* The patch pair must straddle a co\-ordinate plane equally
* Separation between `wedge` patch pairs must be
	+ a single layer of cells
	+ points should appear collocated when viewed in the mid\-plane normal

```
direction

```

* Particles will be snapped to the mid\-plane between pairs of `wedge` patches

## Further information

Source code:

* [Foam::wedgeFvPatchField](https://api.openfoam.com/2606/Foam_wedgeFvPatchField.html)
