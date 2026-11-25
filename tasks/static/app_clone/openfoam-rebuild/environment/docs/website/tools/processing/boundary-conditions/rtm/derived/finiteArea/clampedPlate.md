<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/clampedPlate -->

# clampedPlate

## Description

The `clampedPlate` is a boundary condition that provides
a clamped condition which sets zero fixed value and zero gradient.

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
    type            clampedPlate;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `clampedPlate` | word | yes | \- |

The inherited entries are elaborated in:

* faPatchFields.H

## Further information

Tutorial:

* [obliqueAirJet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/acousticFoam/obliqueAirJet)

Source code:

* [clampedPlate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/clampedPlate)

API:

* [Foam::clampedPlateFaPatchField](https://api.openfoam.com/2606/Foam_clampedPlateFaPatchField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
