<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/rotorDisk -->

# Rotor disk

## Properties

## Usage

The option is specified using:

```
disk1
{
    type            rotorDiskSource;
    selectionMode   cellSet;
    cellSet         rotorDisk1;
    fields          (U);
}

```

## Further information

Tutorials

* [rotorDisk](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/rotorDisk)

Source code

* [rotorDiskSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/rotorDiskSource)
