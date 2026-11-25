<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/constraints/rtm/fixedValue -->

# Fixed value

Enables users to set field values in the domain, irrespective of the local flow
conditions.

## Properties

Downstream fields outside the region constrained will continue developing normally.

No information will be added to the log file other than the identification of the constraint at the start of the simulation.

## Usage

The constraint is available for all primitive field types, i.e. scalar, vector,
sphericalTensor, symTensor and tensor, where the `type` entry is set as

```
type            <type>FixedValueConstraint

```

For example, the scalar variant can be applied to the turbulence `k` and
`epsilon` fields using:

```
fixedValue
{
    type            scalarFixedValueConstraint;
    active          yes;

    selectionMode   cellZone;    //cellZone or all
    cellZone        porosity;
    fieldValues
    {
        k           1;
        epsilon     150;     // any field values can be modified, including scalars.
    }
}

```

## Further information

Tutorials

* [angledDuctExplicitFixedCoeff](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/angledDuctExplicitFixedCoeff)

Source code

* [fixedValueConstraint](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/constraints/general/fixedValueConstraint)
