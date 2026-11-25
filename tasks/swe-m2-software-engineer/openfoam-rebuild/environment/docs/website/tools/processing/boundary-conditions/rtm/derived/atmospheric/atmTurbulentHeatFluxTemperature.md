<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmTurbulentHeatFluxTemperature -->

# atmTurbulentHeatFluxTemperature

## Description

The `atmTurbulentHeatFluxTemperature` is a boundary condition that provides
provides a fixed heat constraint on temperature
(i.e. `T`) to specify temperature gradient through an input heat source
which can either be specified as absolute power \[W], or as flux \[W/m^2].

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
    type            atmTurbulentHeatFluxTemperature;
    heatSource      <word>;
    alphaEff        <word>;
    Cp0             <scalar>;
    q               <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmTurbulentHeatFluxTemperature` | word | yes | \- |
| `heatSource` | Heat source type | word | yes | \- |
| `alphaEff` | Name of turbulent thermal diff. field \[kg/m/s] | word | yes | \- |
| `Cp0` | Specific heat capacity \[m2/s2/K] | Function1\<scalar\> | yes | \- |
| `q` | Heat source value \[W (power) or W/m^2 (flux)] | PatchFunction1\<scalar\> | yes | \- |

Options for the `heatSource` entry:

| Property | Description |
| --- | --- |
| `power` | Absolute power heat source \[W] |
| `flux` | Flux heat source \[W/m^2] |

The inherited entries are elaborated in:

* fixedGradientFvPatchScalarField.H
* Function1\.H
* PatchFunction1\.H

## Further information

Tutorial:

* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code:

* [atmTurbulentHeatFluxTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmTurbulentHeatFluxTemperature)

API:

* [Foam::atmTurbulentHeatFluxTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmTurbulentHeatFluxTemperatureFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
