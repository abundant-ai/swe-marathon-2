<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmNutkWallFunction -->

# atmNutkWallFunction

## Description

The `atmNutkWallFunction` is a boundary condition that provides
a wall constraint on the turbulent viscosity (i.e. `nut`) based on the
turbulent kinetic energy (i.e. `k`) for atmospheric boundary layer modelling.
It is designed to be used in conjunction with the `atmBoundaryLayerInletVelocity`
boundary condition.

The governing equation of the boundary condition:

u\=u∗κln(z\+z0z0) u \= \\frac{u^\*}{\\kappa} ln \\left(\\frac{z \+ z\_0}{z\_0}\\right)u\=κu∗​ln(z0​z\+z0​​)
where:

| Property | Description |
| --- | --- |
| u∗u^\*u∗ | Friction velocity |
| κ\\kappaκ | von Karman constant |
| z0z\_0z0​ | Surface roughness length \[m] |
| zzz | Ground\-normal coordinate |

### References

* Theoretical expressions (tag:HW):

```
Hargreaves, D. M., & Wright, N. G. (2007).
On the use of the k–ε model in commercial CFD software to model
the neutral atmospheric boundary layer.
J. of wind engineering and industrial aerodynamics, 95(5), 355-369.
DOI:10.1016/j.jweia.2006.08.002

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
    type            atmNutkWallFunction;
    z0              <PatchFunction1<scalar>>;

    // Optional entries
    boundNut        <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmNutkWallFunction` | word | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |
| `boundNut` | Flag to zero\-bound nut near wall | bool | no | false |

The inherited entries are elaborated in:

* nutkWallFunctionFvPatchScalarField.H
* PatchFunction1\.H

## Further information

Tutorial:

* [turbineSiting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbineSiting)

Source code:

* [atmNutkWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmNutkWallFunction)

API:

* [Foam::atmNutkWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmNutkWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
