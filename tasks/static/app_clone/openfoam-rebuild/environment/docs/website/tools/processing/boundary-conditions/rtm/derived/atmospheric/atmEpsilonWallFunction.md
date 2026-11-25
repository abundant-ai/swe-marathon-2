<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmEpsilonWallFunction -->

# atmEpsilonWallFunction

## Description

The `atmEpsilonWallFunction` is a boundary condition that provides
a wall constraint on the turbulent kinetic
energy dissipation rate (i.e. `epsilon`) and the turbulent kinetic energy
production contribution (i.e. `G`) for atmospheric boundary layer
modelling.

### References

* Theoretical expressions (tags:PGVB, RH):

```
Parente, A., Gorlé, C., Van Beeck, J., & Benocci, C. (2011).
Improved k–ε model and wall function formulation
for the RANS simulation of ABL flows.
J. of wind engineering and industrial aerodynamics, 99(4), 267-278.
DOI:10.1016/j.jweia.2010.12.017

Richards, P. J., & Hoxey, R. P. (1993).
Appropriate boundary conditions for computational wind
engineering models using the k-ε turbulence model.
In Computational Wind Engineering 1 (pp. 145-153).
DOI:10.1016/B978-0-444-81688-7.50018-8

```

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
    type            atmEpsilonWallFunction;
    z0              <PatchFunction1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmEpsilonWallFunction` | word | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |

The inherited entries are elaborated in:

* epsilonWallFunctionFvPatchScalarField.H
* PatchFunction1\.H

## Further information

Tutorial:

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)

Source code:

* [atmEpsilonWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmEpsilonWallFunction)

API:

* [Foam::atmEpsilonWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmEpsilonWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
