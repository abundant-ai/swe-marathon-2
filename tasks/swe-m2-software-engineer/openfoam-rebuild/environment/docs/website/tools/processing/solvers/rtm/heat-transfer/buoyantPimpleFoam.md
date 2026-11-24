<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/heat-transfer/buoyantPimpleFoam -->

# buoyantPimpleFoam

## Overview

* Category: [Heat transfer](index.md)
* Transient
* Compressible
* [Turbulence](../../../models/turbulence.md)
* [Thermophysical](../../../models/thermophysical.md)
* [fvOptions](../../../../../fundamentals/case-structure/fvoptions.md)

## Usage

### Synopsis

```
buoyantPimpleFoam [OPTIONS]

```

#### Examples

```
buoyantPimpleFoam -region region1

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

#### Files

* [Schemes](../../../numerics/schemes.md)
* [Linear equation solvers](../../../numerics/solvers.md)
* [controlDict](../../../../../fundamentals/case-structure/controldict.md)

#### Fields

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `p` | Pressure \[Pa] | volScalarField | yes | \- |
| `p_rgh` | Pressure \- hydrostatic contribution \[Pa] | volScalarField | yes | \- |
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

The solver employs the [PIMPLE](../../pressure-velocity/pimple.md)
algorithm to solve the following transport equations:

* [Mass transport equation](../../transport-eqns/mass-transport.md)
* [Momentum transport equation](../../transport-eqns/momentum-transport.md)
* [Energy transport equation](../../transport-eqns/energy-transport.md)

## Further information

Tutorial:

* [buoyantPimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantPimpleFoam)

Source code:

* [buoyantPimpleFoam](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/applications/solvers/heatTransfer/buoyantPimpleFoam)

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0)
