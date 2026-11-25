<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/waveSurfacePressure -->

# waveSurfacePressure

## Description

The `waveSurfacePressure` is a pressure boundary condition whose value
is calculated as the hydrostatic pressure based on a given displacement:

p\=−ρ g ζ p \= \-\\rho \\, g \\, \\zetap\=−ρgζ

| Property | Description |
| --- | --- |
| ρ\\rhoρ | Density \[kg/m^3] |
| ggg | Acceleration due to gravity \[m/s^2] |
| ζ\\zetaζ | Wave amplitude \[m] |

The wave amplitude is updated as part of the calculation, derived from the
local volumetric flux.

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
    type            waveSurfacePressure;

    // Optional entries
    phi             <word>;
    zeta            <word>;
    rho             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waveSurfacePressure` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `zeta` | Name of wave\-amplitude field | word | no | zeta |
| `rho` | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* mixedFvPPatchScalarFields.H

* The density field is only required if the flux is mass\-based as opposed to
volumetric\-based.

## Further information

Tutorial:

* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceDyMFoam/oscillatingBox)

Source code:

* [waveSurfacePressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/waveSurfacePressure)

API:

* [Foam::waveSurfacePressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_waveSurfacePressureFvPatchScalarField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
