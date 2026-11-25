<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/buoyancyEnergy -->

# Buoyancy energy

## Properties

Adds the buoyancy energy

S\=ρ(g ∙ U) S \= \\rho (\\vec{g} \\dprod \\vec{U})S\=ρ(g∙U)
## Usage

The option is specified using:

```
buoyancy1
{
    type            buoyancyEnergy;
    selectionMode   all;
}

```

## Further information

Tutorials

* *none*

Source code

* [buoyancyEnergy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/buoyancyEnergy)
