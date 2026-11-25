<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wave/waveVelocity -->

# waveAlpha

## Description

The `waveAlpha` is a boundary condition that establishes
the phase fraction by combining multiple wave models.

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
    type            waveAlpha;

    // Optional entries
    waveDict        <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `waveAlpha` | word | yes | \- |
| `waveDict` | Name of the wave variables dictionary | word | no | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* waveModel.H

## Further information

Tutorial:

* [cnoidal](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/cnoidal)

Source code:

* [waveAlpha](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/waveModels/derivedFvPatchFields/waveAlpha)

API:

* [Foam::waveAlphaFvPatchScalarField](https://api.openfoam.com/2606/Foam_waveAlphaFvPatchScalarField.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
