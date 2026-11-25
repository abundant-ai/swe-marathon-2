<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/alphatWallFunction -->

# alphatWallFunction

## Description

The `alphatWallFunction` is a boundary condition that provides
provides a turbulent thermal diffusivity condition when using wall functions.

The turbulent thermal diffusivity calculated using:

αt\=μtPrt \\alpha\_t \= \\frac{\\mu\_t}{Pr\_t}αt​\=Prt​μt​​
where:

| Property | Description |
| --- | --- |
| αt\\alpha\_tαt​ | Turbulence thermal diffusivity |
| μt\\mu\_tμt​ | Turbulence viscosity |
| PrtPr\_tPrt​ | Turbulent Prandtl number |

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
    type            compressible::alphatWallFunction;

    // Optional entries
    Prt             <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::alphatWallFunction` | word | yes | \- |
| `Prt` | Turbulent Prandtl number | scalar | no | 0\.85 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [roomWithThickCeiling](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/roomWithThickCeiling)

Source code:

* [alphatWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/wallFunctions/alphatWallFunctions/alphatWallFunction)

API:

* [Foam::compressible::alphatWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_alphatWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
