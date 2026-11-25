<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/adjointInletNuaTilda -->

# adjointInletNuaTilda

## Description

The `adjointInletNuaTilda` is a boundary condition that provides
an inlet boundary condition for adjoint `nuaTilda`.

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
    type            adjointInletNuaTilda;
    solverName      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `adjointInletNuaTilda` | word | yes | \- |
| `solverName` | Name of operand solver | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* adjointBoundaryConditions.H

## Further information

Tutorial:

* [motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/adjointOptimisationFoam/shapeOptimisation/motorBike)

Source code:

* [adjointInletNuaTilda](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/adjointInletNuaTilda)

API:

* [Foam::adjointInletNuaTildaFvPatchScalarField](https://api.openfoam.com/2606/Foam_adjointInletNuaTildaFvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
