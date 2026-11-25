<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/buoyancyForce -->

# Buoyancy force

## Properties

Adds the buoyancy force

S\=ρg S \= \\rho \\vec{g}S\=ρg
## Usage

The option is specified using:

```
buoyancy1
{
    type            buoyancyForce;
    selectionMode   all;
    fields          (U);
}

```

## Further information

Tutorials

* *none*

Source code

* [buoyancyForce](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/buoyancyForce)
