<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/optimisation/adjointOutletFlux -->

# adjointOutletFlux

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
    type            adjointOutletFlux;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `adjointOutletFlux` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [adjointOutletFlux](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/optimisation/adjointOptimisation/adjoint/turbulenceModels/incompressibleAdjoint/adjointRAS/derivedFvPatchFields/adjointOutletFlux)

API:

* [Foam::adjointOutletFluxFvPatchField](https://api.openfoam.com/2606/Foam_adjointOutletFluxFvPatchField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
