<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/lumpedMassWallTemperature -->

# lumpedMassWallTemperature

## Description

The `lumpedMassWallTemperature` is a boundary condition that provides
a lumped mass model for temperature.

It considers a single temperature value for the whole patch and evaluates
the temperature evolution using the net heat flux into the patch.

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
    type            lumpedMassWallTemperature;
    Cp              <scalar>;
    mass            <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `lumpedMassWallTemperature` | word | yes | \- |
| `Cp` | Heat capacity \[J/kg/K] | scalar | yes | \- |
| `mass` | Total mass \[kg] | scalar | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H
* temperatureCoupledBase.H

## Further information

Tutorial:

* [hotRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantPimpleFoam/hotRoom)

Source code:

* [lumpedMassWallTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/lumpedMassWallTemperature)

API:

* [Foam::lumpedMassWallTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_lumpedMassWallTemperatureFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
