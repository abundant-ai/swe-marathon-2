<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/region/inclinedFilmNusseltHeight -->

# inclinedFilmNusseltHeight

## Description

The `inclinedFilmNusseltHeight` is boundary condition that provides
a film height boundary condition for inclined films that imposes a
sinusoidal perturbation on top of a mean flow rate, where the height is
calculated using the Nusselt solution.

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
    type            inclinedFilmNusseltHeight;
    GammaMean       <Function1<scalar>>;
    a               <Function1<scalar>>;
    omega           <Function1<scalar>>;

    // Optional entries
    filmRegion      <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `inclinedFilmNusseltHeight` | word | yes | \- |
| `GammaMean` | Mean mass flow rate per unit length \[kg/s/m] | Function1\<scalar\> | yes | \- |
| `a` | Perturbation amplitude \[m] | Function1\<scalar\> | yes | \- |
| `omega` | Perturbation frequency \[rad/s/m] | Function1\<scalar\> | yes | \- |
| `filmRegion` | Name of film region | word | no | surfaceFilmProperties |

The inherited entries are elaborated in:

* fixedValueFvPatchScalarFields.H

## Further information

Tutorial:

* N/A

Source code:

* [inclinedFilmNusseltHeight](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionModels/surfaceFilmModels/derivedFvPatchFields/inclinedFilmNusseltHeight)

API:

* [Foam::inclinedFilmNusseltHeightFvPatchScalarField](https://api.openfoam.com/2606/Foam_inclinedFilmNusseltHeightFvPatchScalarField.html)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
