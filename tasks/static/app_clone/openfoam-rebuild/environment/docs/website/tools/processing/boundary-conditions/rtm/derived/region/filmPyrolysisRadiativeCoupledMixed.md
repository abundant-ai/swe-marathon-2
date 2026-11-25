<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/filmPyrolysisRadiativeCoupledMixed -->

# filmPyrolysisRadiativeCoupledMixed

## Description

The `filmPyrolysisRadiativeCoupledMixed` is boundary condition that provides
a mixed boundary condition for temperature, to be used in the flow and
pyrolysis regions when a film region model is used.

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
    type            filmPyrolysisRadiativeCoupledMixed;
    Tnbr            <word>;
    qr              <word>;
    filmDeltaDry    <scalar>;
    filmDeltaWet    <scalar>;

    // Optional entries
    filmRegion      <word>;
    pyrolysisRegion  <word>;
    convectiveScaling  <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `filmPyrolysisRadiativeCoupledMixed` | word | yes | \- |
| `Tnbr` | Name of field on the neighbour region | word | yes | \- |
| `qr` | Name of the radiative heat flux | word | yes | \- |
| `filmDeltaDry` | Minimum delta film to be considered dry | scalar | yes | \- |
| `filmDeltaWet` | Maximum delta film to be considered wet | scalar | yes | \- |
| `pyrolysisRegion` | Name of pyrolysis region | word | no | pyrolysisProperties |
| `filmRegion` | Name of film region | word | no | surfaceFilmProperties |
| `convectiveScaling` | Convective scaling factor | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* mixedFvPatchFields.H
* pyrolysisModel.H
* temperatureCoupledBase.H

## Further information

Tutorial:

* [flameSpreadWaterSuppressionPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/flameSpreadWaterSuppressionPanel)

Source code:

* [filmPyrolysisRadiativeCoupledMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/regionCoupling/derivedFvPatchFields/filmPyrolysisRadiativeCoupledMixed)

API:

* [Foam::filmPyrolysisRadiativeCoupledMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_filmPyrolysisRadiativeCoupledMixedFvPatchScalarField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
