<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/filmPyrolysisTemperatureCoupled -->

# filmPyrolysisTemperatureCoupled

## Description

The `filmPyrolysisTemperatureCoupled` is boundary condition
designed to be used in conjunction with surface
film and pyrolysis modelling. It provides a temperature boundary condition
for patches on the primary region based on whether the patch is seen to
be 'wet', retrieved from the film alpha field.

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
    type            filmPyrolysisTemperatureCoupled;

    // Optional entries
    filmRegion      <word>;
    pyrolysisRegion  <word>;
    phi             <word>;
    rho             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `filmPyrolysisTemperatureCoupled` | word | yes | \- |
| `pyrolysisRegion` | Name of pyrolysis region | word | no | pyrolysisProperties |
| `filmRegion` | Name of film region | word | no | surfaceFilmProperties |
| `phi` | Name of flux region | word | no | phi |
| `rho` | Name of density region | word | no | rho |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [filmPyrolysisTemperatureCoupled](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/regionCoupling/derivedFvPatchFields/filmPyrolysisTemperatureCoupled)

API:

* [Foam::filmPyrolysisTemperatureCoupledFvPatchScalarField](https://api.openfoam.com/2606/Foam_filmPyrolysisTemperatureCoupledFvPatchScalarField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
