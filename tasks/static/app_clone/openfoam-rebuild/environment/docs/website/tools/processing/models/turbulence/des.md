<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des -->

# Detached Eddy Simulation (DES)

Detached Eddy Simulation relates to a hybrid [RAS](ras/index.md)\-[LES](les/index.md)
approach to turbulence modelling, aiming to alleviate the costly near\-wall
meshing requirements imposed by LES.

## Options

* [k\-ω\-SST Delayed Detached Eddy Simulation (DDES)](des/rtm/kOmegaSSTDDES.md)
* [k\-ω\-SST Detached Eddy Simulation (DES)](des/rtm/kOmegaSSTDES.md)
* [k\-ω\-SST Improved Delayed Detached Eddy Simulation (IDDES)](des/rtm/kOmegaSSTIDDES.md)
* [Spalart\-Allmaras Delayed Detached Eddy Simulation (DDES)](des/rtm/SpalartAllmarasDDES.md)
* [Spalart\-Allmaras Detached Eddy Simulation (DES)](des/rtm/SpalartAllmarasDES.md)
* [Spalart\-Allmaras Improved Delayed Detached Eddy Simulation (IDDES)](des/rtm/SpalartAllmarasIDDES.md)

## Usage

DES is implemented as a subset of [LES](les/index.md), selected by setting the
`simulationType` entry

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
[RAS](ras/index.md) modelling.

## Wall modelling

* [Wall functions](ras/wall-functions/index.md)

## Further information

Source code:

* [DES](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/DES)

Related:

* [Source documentation](https://api.openfoam.com/2606/grpDESTurbulence.html)
