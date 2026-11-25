<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/setFlow -->

# setFlow

## Description

The `setFlow` function object
provides options to set the velocity and flux fields as a function of time.

Useful for testing advection behaviour of numerical schemes by e.g.
imposing solid body rotation, vortex flows. All types include a scaling
`Foam::Function1` type enabling the strength of the transformation to vary as
a function of time.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `setFlow` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
setFlow1
{
    // Mandatory entries (unmodifiable)
    type            setFlow;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    mode        rotation;
    scale       1;

    // Optional entries (runtime modifiable)
    U           U;
    rho         none;
    phi         phi;
    reverseTime 1;

    // When mode=function
    velocity    (1 0 0);

    // When mode=rotation
    omega       6.28318530718;
    origin      (0.5 0 0.5);
    refDir      (1 0 0);
    axis        (0 1 0);

    // When mode=(vortex2D|vortex3D)
    origin      (0.5 0 0.5);
    refDir      (1 0 0);
    axis        (0 1 0);

    // Optional (inherited) entries
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: setFlow | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| mode | Operating mode \- see below | word | yes | \- |
| scale | Scaling function | Function1\<scalar\> | yes | \- |
| U | Name of velocity field | word | no | U |
| rho | Name of density field | word | no | none |
| phi | Name of flux field | word | no | phi |
| reverseTime | Specified time to reverse flow direction | scalar | no | VGREAT |
| velocity | Velocity function | Function1\<vector\> | conditional | \- |
| omega | Rotational speed function | Function1\<scalar\> | conditional | \- |
| origin | Rotation vector origin | vector | conditional | \- |
| refDir | Rotation vector reference direction | vector | conditional | \- |
| axis | Rotation vector axis | vector | conditional | \- |

Options for the `mode` entry:

```
function
rotation
vortex2D
vortex3D

```

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)
* [discInReversedVortexFlow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interIsoFoam/discInReversedVortexFlow)

Source code:

* [setFlow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/setFlow)

API:

* [Foam::functionObjects::setFlow](https://api.openfoam.com/2606/Foam_functionObjects_setFlow.html)

**History:** Introduced in version [v1706](https://www.openfoam.com/news/main-news/openfoam-v1706)
