<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/specularRadiation -->

# specularRadiation

## Description

The `specularRadiation` is a mixed boundary condition that
provides a specular radiation condition for
axisymmetric and symmetry\-plane `fvDOM` computations.

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
    type            specularRadiation;

    // Optional entries
    interpolate         <bool>;

    // Inherited entries
    patchType           <word>;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `specularRadiation` | word | yes | \- |
| `interpolate` | Flag to enable ray\-intensity interp | bool | no | false |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [specularRadiation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/specularRadiation)

API:

* [Foam::radiation::specularRadiationMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_specularRadiationMixedFvPatchScalarField.html)

**History:** Introduced in version [v2306](https://www.openfoam.com/news/main-news/openfoam-v2306)
