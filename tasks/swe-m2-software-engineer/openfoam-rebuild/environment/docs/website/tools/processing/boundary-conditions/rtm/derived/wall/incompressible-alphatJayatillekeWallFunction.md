<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/incompressible-alphatJayatillekeWallFunction -->

# incompressible::alphatJayatillekeWallFunction

## Description

The `incompressible::alphatJayatillekeWallFunction` is boundary condition that
provides a kinematic turbulent thermal conductivity
for using wall functions, using the Jayatilleke 'P' function.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            alphatJayatillekeWallFunction;
    Prt             <scalar>;

    // Optional entries
    kappa           <scalar>;
    E               <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `alphatJayatillekeWallFunction` | word | yes | \- |
| `Prt` | Turbulent Prandtl number | scalar | yes | \- |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `E` | Wall roughness parameter | scalar | no | 9\.8 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [hotRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantBoussinesqPimpleFoam/hotRoom)

Source code:

* [alphatJayatillekeWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/incompressible/turbulentTransportModels/derivedFvPatchFields/wallFunctions/alphatWallFunctions/alphatJayatillekeWallFunction)

API:

* [Foam::incompressible::alphatJayatillekeWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_incompressible_alphatJayatillekeWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
