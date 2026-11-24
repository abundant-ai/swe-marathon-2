<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/meshMotion/compressible-thermalBaffle -->

# compressible\-thermalBaffle

## Description

The `compressible::thermalBaffle` is a boundary condition that provides a
coupled temperature condition between multiple mesh regions.

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
    type            thermalBaffle;

    // Optional entries
    internal        <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible-thermalBaffle` | word | yes | \- |
| `internal` | Flag to deduce if the baffle is internal | bool | no | true |

The inherited entries are elaborated in:

* turbulentTemperatureRadCoupledMixedFvPatchScalarField.H
* thermalBaffleModel.H
* extrudePatchMesh.H

## Further information

Tutorial:

* [roomWithThickCeiling](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/roomWithThickCeiling)

Source code:

* [thermalBaffle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/thermalBaffleModels/derivedFvPatchFields/thermalBaffle)

API:

* [Foam::compressible::thermalBaffleFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_thermalBaffleFvPatchScalarField.html)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
