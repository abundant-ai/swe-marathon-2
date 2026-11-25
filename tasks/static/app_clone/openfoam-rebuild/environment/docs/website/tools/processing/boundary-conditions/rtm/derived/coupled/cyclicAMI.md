<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/cyclicAMI -->

# Cyclic Arbitrary Mesh Interface (AMI)

## Properties

* Coupling condition between a pair of patches that share the same outer bounds,
but whose inner construction may be dissimilar.

## Usage

The condition requires entries in both the `boundary` and field files. Mesh

`boundary` file:

```
<patchName>
{
    type            cyclicAMI;
    neighbourPatch  <coupled patch name>;
    transform       <transform type>;
    ...
}

```

Field file:

```
<patchName>
{
    type            cyclicAMI;
}

```

The `transform` describes the operation required to map the `neighbour` patch
on to the `owner` patch. Options include:

* `noOrdering`: no mapping defined, i.e. the operation is determined by the
patch
* `coincidentFullMatch`: no transform defined and checks that the patch faces
are matched
* `rotational`: rotational about an axis of rotation
* `translational`: translational

## Further information

Related:

* [Cyclic condition](cyclic.md)

Source code:

* [Foam::cyclicAMIPolyPatch](https://api.openfoam.com/2606/Foam_cyclicAMIPolyPatch.html)
* [Foam::cyclicAMIFvPatch](https://api.openfoam.com/2606/Foam_cyclicAMIFvPatch.html)
* [Foam::cyclicAMIFvPatchField](https://api.openfoam.com/2606/Foam_cyclicAMIFvPatchField.html)

Example usage:

* pimpleFoam `mixerVesselAMI2D` tutorial:
[mixerVesselAMI2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/mixerVesselAMI2D)
* pimpleFoam `propeller` tutorial:
[propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
* compressibleInterFoam `sphereDrop` tutorial:
[sphereDrop](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/compressibleInterDyMFoam/laminar/sphereDrop)
