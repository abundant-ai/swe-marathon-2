<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/adjointFarFieldTMVar2 -->

# adjointFarFieldTMVar2

## Description

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
    type            adjointFarFieldTMVar2;
    solverName      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `adjointFarFieldTMVar2` | word | yes | \- |
| `solverName` | Name of operand solver | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* adjointBoundaryConditions.H

## Further information

Tutorial:

* [lift](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/adjointOptimisationFoam/shapeOptimisation/naca0012/kOmegaSST/lift)

Source code:

* [adjointFarFieldTMVar2](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/adjointFarFieldTMVar2)

API:

* [Foam::adjointFarFieldTMVar2FvPatchScalarField](https://api.openfoam.com/2606/Foam_adjointFarFieldTMVar2FvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
