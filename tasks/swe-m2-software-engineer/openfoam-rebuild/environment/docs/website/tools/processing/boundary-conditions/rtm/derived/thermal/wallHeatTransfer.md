<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/wallHeatTransfer -->

# wallHeatTransfer

## Description

The `wallHeatTransfer` is a boundary condition that provides
an enthalpy condition for wall heat transfer.

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
    type            wallHeatTransfer;
    Tinf            <scalarField>;
    alphaWall       <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `wallHeatTransfer` | word | yes | \- |
| `Tinf` | Temperature at the wall | scalarList | yes | \- |
| `alphaWall` | Thermal diffusivity at the wall | scalarList | yes | \- |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [wallHeatTransfer](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/wallHeatTransfer)

API:

* [Foam::wallHeatTransferFvPatchScalarField](https://api.openfoam.com/2606/Foam_wallHeatTransferFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
