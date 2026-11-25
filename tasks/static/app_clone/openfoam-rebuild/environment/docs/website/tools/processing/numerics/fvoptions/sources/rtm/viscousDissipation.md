<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/viscousDissipation -->

# Viscous dissipation

## Properties

## Usage

The option is specified using:

```
dissipation1
{
    type            viscousDissipation;
    selectionMode   cellSet;
    cellSet         sourceCells1;
}

```

## Further information

Tutorials

* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/TJunction)
* [TJunctionArrheniusBirdCarreauTransport](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunctionArrheniusBirdCarreauTransport)
* [mixerVessel2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/multiphaseInterFoam/laminar/mixerVessel2D)

Source code

* [viscousDissipation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/viscousDissipation)
