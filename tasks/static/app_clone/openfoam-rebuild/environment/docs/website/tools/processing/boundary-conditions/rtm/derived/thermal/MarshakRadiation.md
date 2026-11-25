<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/MarshakRadiation -->

# MarshakRadiation

## Description

The `MarshakRadiation` is a mixed boundary condition that
provides a Marshak condition for the incident radiation field
(usually written as `G`).

The radiation temperature is retrieved from the mesh database, using a
user specified temperature field name.

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
    type            MarshakRadiation;

    // Optional entries
    T               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `MarshakRadiation` | word | yes | \- |
| `T` | Name of temperature field | word | no | T |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* [hotRadiationRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/hotRadiationRoom)

Source code:

* [MarshakRadiation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/MarshakRadiation)

API:

* [Foam::radiation::MarshakRadiationFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_MarshakRadiationFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
