<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/fixedMultiPhaseHeatFlux -->

# fixedMultiPhaseHeatFlux

## Description

The `compressible::fixedMultiPhaseHeatFlux` is a boundary condition that
calculates a wall temperature that produces
the specified overall wall heat flux across
all the phases in an Eulerian multi\-phase simulation.

Intended to be used with the `copiedFixedValue` condition
to ensure that phase wall temperature are consistent:

* Set `fixedMultiPhaseHeatFlux` boundary for one of the phases
* Use `copiedFixedValue` for all the other phases.

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
    type            fixedMultiPhaseHeatFlux;
    q               <scalarField>;

    // Optional entries
    relax           <scalar>;
    Tmin            <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedMultiPhaseHeatFlux` | word | yes | \- |
| `q` | Heat power \[W] or flux \[W/m^2] | scalarField | yes | \- |
| `relax` | Relaxation factor | scalar | no | 1\.0 |
| `Tmin` | Minimum temperature limit \[K] | scalar | no | 273\.0 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [wallBoilingIATE](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/wallBoilingIATE)

Source code:

* [fixedMultiPhaseHeatFlux](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/fixedMultiPhaseHeatFlux)

API:

* [Foam::fixedMultiPhaseHeatFluxFvPatchScalarField](https://api.openfoam.com/2606/Foam_fixedMultiPhaseHeatFluxFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
