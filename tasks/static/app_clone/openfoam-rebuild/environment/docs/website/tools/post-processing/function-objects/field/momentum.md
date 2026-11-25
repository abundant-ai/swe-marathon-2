<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/momentum -->

# momentum

## Description

The `momentum` function object
computes linear/angular momentum, reporting integral values
and optionally writing the fields.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `momentum` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
momentum1
{
    // Mandatory entries (unmodifiable)
    type            momentum;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    regionType      all;
    writeMomentum   yes;
    writePosition   yes;
    writeVelocity   yes;
    p               p;
    U               U;
    rho             rho;
    rhoRef          1.0;

    cylindrical     true;
    origin          (0 0 0);
    e1              (1 0 0);
    e3              (0 0 1);

    // Optional (inherited) entries
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
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
| type | Type name: momentum | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| regionType | Selection type: all/cellSet/cellZone | word | no | all |
| writeMomentum | Write (linear, angular) momentum fields | bool | no | no |
| writePosition | Write angular position component fields | bool | no | no |
| writeVelocity | Write angular velocity fields | bool | no | no |
| p | Pressure field name | word | no | p |
| U | Velocity field name | word | no | U |
| rho | Density field name | word | no | rho |
| rhoRef | Reference density (incompressible) | scalar | no | 1\.0 |
| cylindrical | Use cylindrical coordinates | bool | no | no |
| origin | Origin for cylindrical coordinates | vector | conditional | \- |
| name | Name of cellSet/cellZone if required | word | conditional | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

* For incompressible cases, the value of `rhoRef` is used.
* When specifying the cylindrical coordinate system, the rotation can be
specified directly with e1/e2/e3 axes, or via a `rotation` sub\-dictionary.

For example:

```
origin      (0 0 0);
rotation
{
    type    cylindrical;
    axis    (0 0 1);
}

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `momentum_x` : x\-component of momentum
* `momentum_y` : y\-component of momentum
* `momentum_z` : z\-component of momentum
* `momentum_r` : r\-component of angular momentum
* `momentum_theta` : theta\-component of angular momentum
* `momentum_axis` : axial\-component of angular momentum

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [momentum](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/momentum)

API:

* [Foam::functionObjects::momentum](https://api.openfoam.com/2606/Foam_functionObjects_momentum.html)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812)
