<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/externalWallHeatFluxTemperature -->

# externalWallHeatFluxTemperature

## Description

The `externalWallHeatFluxTemperature` is a boundary condition that
applies a heat flux condition to temperature on an external wall in
one of three modes:

* fixed power: supply Q
* fixed heat flux: supply q
* fixed heat transfer coefficient: supply h and Ta

where:

| Property | Description |
| --- | --- |
| Q | Power \[W] |
| q | Heat flux \[W/m^2] |
| h | Heat transfer coefficient \[W/m^2/K] |
| Ta | Ambient temperature \[K] |

For heat transfer coefficient mode optional thin thermal layer resistances
can be specified through thicknessLayers and kappaLayers entries.

The thermal conductivity `kappa` can either be retrieved from various
possible sources, as detailed in the class `temperatureCoupledBase`.

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
    type            externalWallHeatFluxTemperature;
    mode            <word>;

    // Optional entries
    relaxation      <scalar>;
    emissivity      <scalar>;
    qrRelaxation    <scalar>;
    qr              <word>;

    // Conditional entries

        // if mode==power
        Q           <Function1<scalar>>;

        // if mode==flux
        q           <PatchFunction1<scalar>>;

        // if mode==coefficient
        h           <PatchFunction1<scalar>>;
        Ta          <Function1<scalar>>;
        thicknessLayers <scalarField>;
        kappaLayers <scalarField>;

        // if qr!=none
        qrPrevious  <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `externalWallHeatFluxTemperature` | word | yes | \- |
| `mode` | Operation mode | word | yes | \- |
| `relaxation` | Relaxation factor for wall temperature | scalar | no | 1\.0 |
| `emissivity` | Surface emissivity for radiative flux | scalar | no | 0\.0 |
| `qrRelaxation` | Relaxation factor for radiative field | scalar | no | 1\.0 |
| `qr` | Name of radiative field | word | no | none |
| `Q` | Heat power \[W] | Function1\<scalar\> | conditional | \- |
| `q` | Heat flux \[W/m^2] | PatchFunction1\<scalar\> | conditional | \- |
| `h` | Heat transfer coeff \[W/m^2/K] | PatchFunction1\<scalar\> | conditional | \- |
| `Ta` | Ambient temperature \[K] | PatchFunction1\<scalar\> | conditional | \- |
| `qrPrevious` | Cached field for qr relaxation | scalarField | conditional | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H
* temperatureCoupledBase.H
* PatchFunction1\.H

## Further information

Tutorial:

* [externalSolarLoad](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/externalSolarLoad)

Source code:

* [externalWallHeatFluxTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/externalWallHeatFluxTemperature)

API:

* [Foam::externalWallHeatFluxTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_externalWallHeatFluxTemperatureFvPatchScalarField.html)

**History:** Introduced in version [2206](https://www.openfoam.com/news/main-news/openfoam-2206)
