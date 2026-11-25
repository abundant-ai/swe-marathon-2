<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmOmegaWallFunction -->

# atmOmegaWallFunction

## Description

The `atmOmegaWallFunction` is a boundary condition that provides
a wall constraint on the specific dissipation rate (i.e. `omega`) and
the turbulent kinetic energy production contribution (i.e. `G`) for
atmospheric boundary layer modelling.

### References

* Theoretical expressions (tags:PGVB, B):

```
Parente, A., Gorlé, C., Van Beeck, J., & Benocci, C. (2011).
Improved k–ε model and wall function formulation
for the RANS simulation of ABL flows.
J. of wind engineering and industrial aerodynamics, 99(4), 267-278.
DOI:10.1016/j.jweia.2010.12.017

Bredberg, J. (2000).
On the wall boundary condition for turbulence models.
Chalmers University of Technology, Depart. of Thermo and Fluid Dyn.
Internal Report 00/4. Sweden: Göteborg.

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
    type            atmOmegaWallFunction;
    z0              <PatchFunction1<scalar>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmOmegaWallFunction` | word | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |

The inherited entries are elaborated in:

* omegaWallFunctionFvPatchScalarField.H
* PatchFunction1\.H

## Further information

Tutorial:

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)

Source code:

* [atmOmegaWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmOmegaWallFunction)

API:

* [Foam::atmOmegaWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmOmegaWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
