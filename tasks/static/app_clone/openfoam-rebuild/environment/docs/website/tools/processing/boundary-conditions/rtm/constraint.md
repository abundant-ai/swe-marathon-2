<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/constraint -->

# Geometric constraint conditions

Some cases can be reduced to their equivalent simplified systems by taking
advantage of dimensionality, symmetric and cyclic behaviour. In OpenFOAM,
this is achieved by the application of *constraint* conditions, e.g. for

* 2\-D cases: empty, wedge
* reduced geometry cases: symmetry, cyclic
* parallel cases: processor

## Options

Available constraint conditions include

* [Empty](constraint/empty.md)
* [Processor](constraint/processor.md)
* [Symmetry plane](constraint/symmetryPlane.md)
* [Wedge](constraint/wedge.md)

## Boundary mesh type

Constraint conditons are specified using the `<constraint type>` type entry
in the `$FOAM_CASE/constant/polyMesh/boundary` file:

```
patchName
{
    type            <constraint type>;
    ...
}

```

## Field type

The field type entry typically takes the same value as the boundary mesh type,
with additional properties as required

```
patchName
{
    type            <constraint type>;
    ...
}

```

## Further information

Source code:

* [constraint](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/constraint)

See also

* [grpConstraintBoundaryConditions](https://api.openfoam.com/2606/grpConstraintBoundaryConditions.html)
