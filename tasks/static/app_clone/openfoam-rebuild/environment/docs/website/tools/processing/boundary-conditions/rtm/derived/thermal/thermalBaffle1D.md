<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/thermalBaffle1D -->

# thermalBaffle1D

## Description

The `thermalBaffle1D` is a boundary condition that solves a steady 1D thermal baffle.

The solid properties are specify as dictionary. Optionally radiative heat
flux (qr) can be incorporated into the balance. Some under\-relaxation might
be needed on qr. Baffle and solid properties need to be specified on the
master side of the baffle.

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
    type            thermalBaffle1D;

    // Optional entries
    baffleActivated <bool>;
    qrRelaxation    <scalar>;
    qr              <word>;
    thickness       <scalarField>;
    qs              <scalarField>;
    qrPrevious      <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `thermalBaffle1D` | word | yes | \- |
| `baffleActivated` | Flag to enable baffle | bool | no | true |
| `qrRelaxation` | Relaxation factor for qr solution | scalar | no | 1\.0 |
| `qr` | Name of qr field | word | no | none |
| `thickness` | Baffle thickness field | scalarField | no | \- |
| `qs` | Superficial heat source \[W/m^2] | scalarField | no | \- |
| `qrPrevious` | Cache for qr field | scalarField | no | \- |

The inherited entries are elaborated in:

* mappedPatchBase.H
* mixedFvPatchFields.H

## Further information

Tutorial:

* [circuitBoardCooling](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/circuitBoardCooling)

Source code:

* [thermalBaffle1D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/thermalBaffle1D)

API:

* [Foam::compressible::thermalBaffle1DFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_thermalBaffle1DFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
