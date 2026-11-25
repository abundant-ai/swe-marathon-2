<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmAlphatkWallFunction -->

# atmAlphatWallFunction

## Description

The `atmAlphatWallFunction` is a boundary condition that provides
a wall constraint on the kinematic turbulent thermal conductivity
(i.e. `alphat`) for atmospheric boundary layer modelling. It assumes a
logarithmic distribution of the potential temperature within the first cell.

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
    type            atmAlphatWallFunction;
    Pr              <Function1<scalar>>;
    Prt             <PatchFunction1<scalar>>;
    z0              <PatchFunction1<scalar>>;

    // Optional entries
    Cmu             <scalar>;
    kappa           <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmAlphatWallFunction` | word | yes | \- |
| `Pr` | Molecular Prandtl number | Function1\<scalar\> | yes | \- |
| `Prt` | Turbulent Prandtl number | PatchFunction1\<scalar\> | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |
| `Cmu` | Empirical model constant | scalar | no | 0\.09 |
| `kappa` | von Karman constant | scalar | no | 0\.41 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* Function1\.H
* PatchFunction1\.H

## Further information

Tutorial:

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)

Source code:

* [atmAlphatkWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmAlphatkWallFunction)

API:

* [Foam::atmAlphatkWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmAlphatkWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
