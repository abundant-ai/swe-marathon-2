<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/waWallFunction -->

# waWallFunction

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
    type            waWallFunction;
    solverName      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waWallFunction` | word | yes | \- |
| `solverName` | Name of operand solver | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* adjointBoundaryConditions.H

## Further information

Tutorial:

* [opt](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/adjointOptimisationFoam/shapeOptimisation/sbend/turbulent/kOmegaSST/opt)

Source code:

* [waWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/waWallFunction)

API:

* [Foam::waWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_waWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
