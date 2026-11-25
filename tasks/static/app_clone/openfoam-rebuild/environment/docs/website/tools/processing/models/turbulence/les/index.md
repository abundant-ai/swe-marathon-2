<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/ -->

# Large Eddy Simulation (LES)

## Options

* [Dynamic k equation](rtm/dynamicKEqn.md)
* [k equation](rtm/kEqn.md)
* [Smagorinsky](rtm/Smagorinsky.md)
* [Wall Adapting Local Eddy\-viscosity (WALE)](rtm/WALE.md)

## Usage

LES is selected by setting the `simulationType` entry

```
simulationType  LES;

LES
{
    // Model input parameters
}

```

Suitable for:

* 3\-D cases, not appropriate for reduced\-dimension cases
* transient, not appropriate for steady state

## Initialisation

Typically initialised from a precursor calculation, e.g. employing
[RAS](../ras/index.md) modelling.

## LES Deltas

* [Cube\-root volume](delta/rtm/cubeRootVol.md)
* [Van Driest](delta/rtm/vanDriest.md)

## Further information

Source code:

* [LES](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/LES)

Related:

* [Source documentation](https://api.openfoam.com/2606/grpLESTurbulence.html)
