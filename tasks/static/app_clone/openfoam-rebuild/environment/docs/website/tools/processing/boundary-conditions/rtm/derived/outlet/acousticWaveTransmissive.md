<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/acousticWaveTransmissive -->

# acousticWaveTransmissive

## Description

The `acousticWaveTransmissive` boundary condition provides a wave transmissive
outflow condition by solving the following governing equation at the boundary:

D WfDt\=0 \\frac{D \\, W f}{D t} \= 0DtDWf​\=0
where WWW represents the wave speed and fff corresponds to the field to
which this boundary condition is applied.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type                patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                acousticWaveTransmissive;
    advectiveSpeed      <scalar>;

    // Inherited entries
    ...
}

```

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `acousticWaveTransmissive` | word | yes | \- |
| `advectiveSpeed` | Advective speed value | scalar | yes | \- |

The inherited entries are elaborated in:

* [Foam::advectiveFvPatchField](https://api.openfoam.com/2606/Foam_advectiveFvPatchField.html)

## Further information

Tutorial:

* [obliqueAirJet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/acousticFoam/obliqueAirJet)

Source code:

* [Foam::acousticWaveTransmissiveFvPatchField](https://api.openfoam.com/2606/Foam_acousticWaveTransmissiveFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5) ]
