<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/greyDiffusiveRadiation -->

# greyDiffusiveRadiation

## Description

The `greyDiffusiveRadiation` is a boundary condition that
provides a grey\-diffuse condition for radiation intensity, `I`, for use with
the finite\-volume discrete\-ordinates model (fvDOM), in which the radiation
temperature is retrieved from the temperature field boundary condition.

An external radiative heat flux can be added using `qRadExt`. If
`qRadExtDir` is specified, this ray closest to this direction is used.
Otherwise, the face normal is used as direction to set `qRadExt`.

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
    type            greyDiffusiveRadiation;

    // Optional entries
    T               <word>;
    qRadExt         <scalar>;
    qRadExtDir      <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `greyDiffusiveRadiation` | word | yes | \- |
| `T` | Name of temperature field | word | no | T |
| `qRadExt` | Radiative external flux | scalar | no | 0 |
| `qRadExtDir` | Radiative external flux direction | vector | no | Zero |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* [smallPoolFire2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/smallPoolFire2D)

Source code:

* [greyDiffusiveRadiation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/greyDiffusiveRadiation)

API:

* [Foam::radiation::greyDiffusiveRadiationMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_greyDiffusiveRadiationMixedFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
