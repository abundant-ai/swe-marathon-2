<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/heat-transfer/thermoFoam -->

# thermoFoam

## Overview

* Category: [Heat transfer](index.md)
* Transient
* Frozen flow
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Usage

### Synopsis

```
thermoFoam [OPTIONS]

```

#### Examples

```
thermoFoam -region region1

```

### Input

#### Arguments

No arguments required.
#### Options

```
-case <dir>       Case directory (instead of current directory)
  -decomposeParDict <file>
                    Alternative decomposePar dictionary file
  -dry-run          Check case set-up only using a single time step
  -dry-run-write    Check case set-up and write only using a single time step
  -parallel         Run in parallel
  -postProcess      Execute functionObjects only
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-full        Display full help and exit

```

### Files

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

#### Fields

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `U` | Velocity \[m/s] | volVectorField | yes | \- |
| `T` | Temperature \[K] | volScalarField | yes | \- |

#### Models

* [turbulence](../../../models/turbulence.md):
`constant/turbulenceProperties`
* [heat transfer](../../../models/thermophysical.md#usage):
`constant/thermophysicalModels`
* [finite volume options](../../../numerics/fvoptions.md#usage):
`constant/fvOptions` (optional)

## Method

The solver can employ the [SIMPLE](../../pressure-velocity/simple.md)
or the [PIMPLE](../../pressure-velocity/pimple.md) algorithm to solve the
energy transport equation on a frozen flow field:

* [Energy transport equation](../../transport-eqns/energy-transport.md)

## Further information

Tutorial:

* *None*

Source code:

* [thermoFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/heatTransfer/thermoFoam)

**History:** Introduced in version [2\.2\.0](https://www.openfoam.com/news/main-news/openfoam-2.2.0)
