<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/adjointOutletNuaTildaFlux -->

# adjointOutletNuaTildaFlux

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
    type            adjointOutletNuaTildaFlux;
    solverName      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `adjointOutletNuaTildaFlux` | word | yes | \- |
| `solverName` | Name of operand solver | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* adjointBoundaryConditions.H

## Further information

Tutorial:

* N/A

Source code:

* [adjointOutletNuaTildaFlux](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/adjointOutletNuaTildaFlux)

API:

* [Foam::adjointOutletNuaTildaFluxFvPatchScalarField](https://api.openfoam.com/2606/Foam_adjointOutletNuaTildaFluxFvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
