<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/wideBandDiffusiveRadiation -->

# wideBandDiffusiveRadiation

## Description

The `wideBandDiffusiveRadiation` is a mixed boundary condition that
provides a wide\-band, diffusive radiation
condition, where the patch temperature is specified.

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
    type            wideBandDiffusiveRadiation;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `wideBandDiffusiveRadiation` | word | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* [solarBeamWithTrees](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/chtMultiRegionFoam/solarBeamWithTrees)

Source code:

* [wideBandDiffusiveRadiation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/wideBandDiffusiveRadiation)

API:

* [Foam::radiation::wideBandDiffusiveRadiationMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_wideBandDiffusiveRadiationMixedFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
