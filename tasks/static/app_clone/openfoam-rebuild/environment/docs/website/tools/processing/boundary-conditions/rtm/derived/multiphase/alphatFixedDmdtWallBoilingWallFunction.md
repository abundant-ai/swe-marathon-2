<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/alphatFixedDmdtWallBoilingWallFunction -->

# alphatFixedDmdtWallBoilingWallFunction

## Description

The `alphatFixedDmdtWallBoilingWallFunction` is a boundary condition that provides
a simple `alphatPhaseChangeJayatillekeWallFunction` condition with
a fixed volumetric phase\-change mass flux.

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
    type         compressible::alphatFixedDmdtWallBoilingWallFunction;
    vaporPhase   <word>;

    // Optional entries
    relax        <scalar>;
    fixedDmdt    <scalar>;
    L            <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::alphatFixedDmdtWallBoilingWallFunction` | word | yes | \- |
| `vaporPhase` | Name of the vapor phase | word | yes | \- |
| `relax` | Relaxation factor for dmdt | scalar | no | 1\.0 |
| `fixedDmdt` | Volumetric phase\-change mass flux in near wall cells | scalar | no | 0\.0 |
| `L` | Latent heat | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* alphatPhaseChangeJayatillekeWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* N/A

Source code:

* [alphatFixedDmdtWallBoilingWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/alphatFixedDmdtWallBoilingWallFunction)

API:

* [Foam::compressible::alphatFixedDmdtWallBoilingWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatFixedDmdtWallBoilingWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
