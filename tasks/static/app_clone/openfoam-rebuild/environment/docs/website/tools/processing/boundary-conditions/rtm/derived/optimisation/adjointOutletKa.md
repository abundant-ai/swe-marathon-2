<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/adjointOutletKa -->

# adjointOutletKa

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
    type            adjointOutletKa;
    solverName      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `adjointOutletKa` | word | yes | \- |
| `solverName` | Name of operand solver | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* adjointBoundaryConditions.H

## Further information

Tutorial:

* [opt](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/adjointOptimisationFoam/shapeOptimisation/sbend/turbulent/kOmegaSST/opt)

Source code:

* [adjointOutletKa](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/adjointOutletKa)

API:

* [Foam::adjointOutletKaFvPatchScalarField](https://api.openfoam.com/2606/Foam_adjointOutletKaFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
