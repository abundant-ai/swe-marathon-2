<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/alphatPhaseChangeJayatillekeWallFunction -->

# alphatPhaseChangeJayatillekeWallFunction

## Description

The `compressible::alphatPhaseChangeJayatillekeWallFunction` is a boundary condition that provides
a thermal wall function for turbulent thermal diffusivity (usually `alphat`)
based on the Jayatilleke model for the Eulerian multiphase solvers.

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
    type            compressible::alphatPhaseChangeJayatillekeWallFunction;

    // Optional entries
    Prt             <scalar>;
    Cmu             <scalar>;
    kappa           <scalar>;
    E               <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::alphatPhaseChangeJayatillekeWallFunction` | word | yes | \- |
| `Prt` | Turbulent Prandtl number | scalar | no | 0\.85 |
| `Cmu` | Empirical model coefficient | scalar | no | 0\.09 |
| `kappa` | Von Karman constant | scalar | no | 0\.41 |
| `E` | Wall roughness parameter | scalar | no | 9\.8 |

The inherited entries are elaborated in:

* alphatPhaseChangeWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* [wallBoiling](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/wallBoiling)

Source code:

* [alphatPhaseChangeJayatillekeWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/alphatPhaseChangeJayatillekeWallFunction)

API:

* [Foam::compressible::alphatPhaseChangeJayatillekeWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatPhaseChangeJayatillekeWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
