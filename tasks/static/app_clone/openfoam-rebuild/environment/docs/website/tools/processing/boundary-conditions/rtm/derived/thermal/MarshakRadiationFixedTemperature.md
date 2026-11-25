<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/MarshakRadiationFixedTemperature -->

# MarshakRadiationFixedTemperature

## Description

The `MarshakRadiationFixedTemperature` is a mixed boundary condition that
provides a Marshak condition for the incident radiation field (usually written
as `G`).

The radiation temperature field across the patch is supplied by the user
using the `Trad` entry.

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
    type            MarshakRadiationFixedTemperature;
    Trad            <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `MarshakRadiationFixedTemperature` | word | yes | \- |
| `Trad` | Radiation temperature field | scalarField | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [MarshakRadiationFixedTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/MarshakRadiationFixedTemperature)

API:

* [Foam::radiation::MarshakRadiationFixedTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_MarshakRadiationFixedTemperatureFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
