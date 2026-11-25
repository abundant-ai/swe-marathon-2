<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/alphatFilmWallFunction -->

# alphatFilmWallFunction

## Description

The `alphatFilmWallFunction` is boundary condition that provides
a turbulent thermal diffusivity condition
when using wall functions, for use with surface film models. This
condition varies from the standard wall function by taking into account any
mass released from the film model.

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
    type            alphatFilmWallFunction;

    // Optional entries
    filmRegion      <word>;
    B               <scalar>;
    yPlusCrit       <scalar>;
    Cmu             <scalar>;
    kappa           <scalar>;
    Prt             <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `alphatFilmWallFunction` | word | yes | \- |
| `B` | B coefficient | scalar | no | 5\.5 |
| `yPlusCrit` | y\+ value for laminar \-\> turbulent transition | scalar | no | 11\.05 |
| `Cmu` | Empirical model coefficient | scalar | no | 0\.09 |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `Prt` | Turbulent Prandtl number | scalar | no | 0\.85 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [hotBoxes](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/hotBoxes)

Source code:

* [alphatFilmWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/surfaceFilmModels/derivedFvPatchFields/wallFunctions/alphatFilmWallFunction)

API:

* [Foam::compressible::RASModels::alphatFilmWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_RASModels_alphatFilmWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
