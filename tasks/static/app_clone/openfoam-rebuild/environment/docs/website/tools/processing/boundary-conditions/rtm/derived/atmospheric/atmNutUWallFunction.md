<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmNutUWallFunction -->

# atmNutUWallFunction

## Description

The `atmNutUWallFunction` is a boundary condition that provides
a wall constraint on the turbulent viscosity (i.e. `nut`) based on velocity
(i.e. `U`) for atmospheric boundary layer modelling. It is designed to be
used in conjunction with the `atmBoundaryLayerInletVelocity` boundary condition.

The governing equation of the boundary condition:

u\=u∗κln(z\+z0z0) u \= \\frac{u^\*}{\\kappa} ln \\left(\\frac{z \+ z\_0}{z\_0}\\right)u\=κu∗​ln(z0​z\+z0​​)
where:

| Property | Description |
| --- | --- |
| u∗u^\*u∗ | Friction velocity |
| κ\\kappaκ | von Karman constant |
| z0z\_0z0​ | Surface roughness length \[m] |
| zzz | Ground\-normal coordinate |

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
    type            atmNutUWallFunction;
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
| `type` | Type name: `atmNutUWallFunction` | word | yes | \- |
| `z0` | Surface roughness length \[m] | PatchFunction1\<scalar\> | yes | \- |
| `boundNut` | Flag to zero\-bound nut near wall | bool | no | false |

The inherited entries are elaborated in:

* nutUWallFunctionFvPatchScalarField.H
* PatchFunction1\.H

## Further information

Tutorial:

* N/A

Source code:

* [atmNutUWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/wallFunctions/atmNutUWallFunction)

API:

* [Foam::atmNutUWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmNutUWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
