<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/totalFlowRateAdvectiveDiffusive -->

# totalFlowRateAdvectiveDiffusive

## Description

The `totalFlowRateAdvectiveDiffusive` is a boundary condition that provides
an inlet for species. The diffusion and advection fluxes are
considered to calculate the inlet value for the species.

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
    type            totalFlowRateAdvectiveDiffusive;

    // Optional entries
    phi             <word>;
    rho             <word>;
    massFluxFraction <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `totalFlowRateAdvectiveDiffusive` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `massFluxFraction` | Mass flux fraction | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* mixedFvPatchField.H

* The `massFluxFraction` sets the fraction of the flux of each particular
species.

## Further information

Tutorial:

* [simplePMMApanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/simplePMMApanel)

Source code:

* [totalFlowRateAdvectiveDiffusive](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/totalFlowRateAdvectiveDiffusive)

API:

* [Foam::totalFlowRateAdvectiveDiffusiveFvPatchScalarField](https://api.openfoam.com/2606/Foam_totalFlowRateAdvectiveDiffusiveFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
