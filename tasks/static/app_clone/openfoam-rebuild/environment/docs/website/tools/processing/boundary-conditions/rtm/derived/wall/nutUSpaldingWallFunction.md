<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/nutUSpaldingWallFunction -->

# nutUSpaldingWallFunction

## Description

The `nutUSpaldingWallFunction` is boundary condition that provides
a wall function for the turbulent viscosity (i.e. `nut`) based on velocity
(i.e. `U`). Using Spalding's law gives a continuous `nut` profile to the wall.

y\+\=u\+\+1E\[exp(κu\+)−1−κu\+ −0\.5(κu\+)2−16(κu\+)3] y^\+ \= u^\+ \+ \\frac{1}{E} \\left\[exp(\\kappa u^\+) \- 1 \- \\kappa u^\+\\,
 \- 0\.5 (\\kappa u^\+)^2 \- \\frac{1}{6} (\\kappa u^\+)^3\\right]y\+\=u\+\+E1​\[exp(κu\+)−1−κu\+−0\.5(κu\+)2−61​(κu\+)3]
where:

| Property | Description |
| --- | --- |
| y\+y^\+y\+ | Wall\-normal height of a cell centre in wall units |
| u\+u^\+u\+ | Velocity at \\fy\+fy^\+\\fy\+f in wall units |
| κ\\kappaκ | von Karman constant |

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            nutUSpaldingWallFunction;

    // Optional entries
    maxIter         <label>;
    tolerance       <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `nutUSpaldingWallFunction` | word | yes | \- |
| `maxIter` | Number of Newton\-Raphson iterations | label | no | 10 |
| `tolerance` | Convergence tolerance | scalar | no | 0\.0001 |

The inherited entries are elaborated in:

* nutWallFunctionFvPatchScalarField.H

* Suffers from non\-exact restart since `correctNut()` (called through
`turbulence->validate`) returns a slightly different value every time
it is called. This is since the seed for the Newton\-Raphson iteration
uses the current value of `*this (\c =nut )`.
* This can be avoided by overriding the tolerance. This also switches on
a pre\-detection whether the current nut already satisfies the turbulence
conditions and if so does not change it at all. This means that the nut
only changes if it 'has really changed'. This probably should be used with
a tight tolerance, to make sure to kick every iteration, e.g.

```
maxIter     100;
tolerance   1e-7;

```

## Further information

Tutorial:

* [airFoil2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/airFoil2D)

Source code:

* [nutUSpaldingWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions/nutWallFunctions/nutUSpaldingWallFunction)

API:

* [Foam::nutUSpaldingWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutUSpaldingWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
