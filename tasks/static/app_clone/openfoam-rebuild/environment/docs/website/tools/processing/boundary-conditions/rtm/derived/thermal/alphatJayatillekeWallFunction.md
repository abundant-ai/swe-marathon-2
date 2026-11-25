<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/alphatJayatillekeWallFunction -->

# alphatJayatillekeWallFunction

## Description

The `alphatJayatillekeWallFunction` is a boundary condition that provides
a thermal wall function for turbulent thermal diffusivity (usually `alphat`)
based on the Jayatilleke model.

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
    type            compressible::alphatJayatillekeWallFunction;

    // Optional entries
    Prt             <scalar>;
    kappa           <scalar>;
    E               <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::alphatJayatillekeWallFunction` | word | yes | \- |
| `Prt` | Turbulent Prandtl number | scalar | no | 0\.85 |
| `kappa` | von Karman constant | scalar | no | 0\.41 |
| `E` | Wall roughness parameter | scalar | no | 9\.8 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [comfortHotRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/comfortHotRoom)

Source code:

* [alphatJayatillekeWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/wallFunctions/alphatWallFunctions/alphatJayatillekeWallFunction)

API:

* [Foam::compressible::alphatJayatillekeWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatJayatillekeWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
