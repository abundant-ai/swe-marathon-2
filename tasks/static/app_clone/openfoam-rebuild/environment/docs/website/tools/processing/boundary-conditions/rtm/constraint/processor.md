<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/constraint/processor -->

# Processor

## Properties

Applied in pairs to patches that communicate between processors. Usually these
patches are not created manually, but are generated when decomposing the
mesh for parallel cases.

## Usage

The condition requires entries in both the `boundary` and field files. Mesh
`boundary` file:

```
<patchName>
{
    type            processor;
    ...
}

```

Field file:

```
<patchName>
{
    type            processor;
}

```

## Further information

Source code:

* [processor](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/constraint/processor)

API:

* [Foam::processorFvPatchField](https://api.openfoam.com/2606/Foam_processorFvPatchField.html)
