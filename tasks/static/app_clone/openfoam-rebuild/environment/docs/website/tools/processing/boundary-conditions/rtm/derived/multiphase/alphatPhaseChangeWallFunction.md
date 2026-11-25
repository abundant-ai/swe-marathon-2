<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/alphatPhaseChangeWallFunction -->

# alphatPhaseChangeWallFunction

## Description

The `compressible::alphatPhaseChangeWallFunction` is a boundary condition that provides
an abstract base\-class for all `alphatWallFunctions` supporting phase\-change.

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
    // Optional entries
    dmdt        <scalarField>;
    mDotL       <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `dmdt` | Rate of phase\-change | scalarField | no | 0\.0 |
| `mDotL` | Latent heat of the phase\-change | scalarField | no | 0\.0 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [alphatPhaseChangeWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/alphatPhaseChangeWallFunction)

API:

* [Foam::compressible::alphatPhaseChangeWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatPhaseChangeWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
