<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/meanVelocityForce/ -->

# Mean velocity force

## Properties

* Applies a force to maintain a user\-specified volume\-averaged mean velocity,
e.g. useful for channel flow cases

## Usage

The option is specified using:

```
meanVelocity1
{
    type            meanVelocityForce;
    selectionMode   all;
    fields          (U);
    Ubar            (10 0 0);
}

```

Currently only available to incompressible solvers

## Further information

Tutorials

* [periodicPlaneChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/periodicPlaneChannel)

Source code

* [meanVelocityForce](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/meanVelocityForce)
