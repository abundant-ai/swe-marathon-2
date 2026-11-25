<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/nutkFilmWallFunction -->

# nutkFilmWallFunction

## Description

The `nutkFilmWallFunction` is boundary condition that provides
a turbulent viscosity condition when
using wall functions, based on turbulence kinetic energy, for use with
surface film models.

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
    type            nutkFilmWallFunction;

    // Optional entries
    filmRegion      <word>;
    B               <scalar>;
    yPlusCrit       <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutkFilmWallFunction` | word | yes | \- |
| `B` | B coefficient | scalar | no | 5\.5 |
| `yPlusCrit` | y\+ value for laminar \-\> turbulent transition | scalar | no | 11\.05 |

The inherited entries are elaborated in:

* nutkWallFunctionFvPatchScalarField.H

## Further information

Tutorial:

* [hotBoxes](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/hotBoxes)

Source code:

* [nutkFilmWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/surfaceFilmModels/derivedFvPatchFields/wallFunctions/nutkFilmWallFunction)

API:

* [Foam::compressible::RASModels::nutkFilmWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_RASModels_nutkFilmWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
