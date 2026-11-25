<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/RNGkEpsilon -->

# RNG k\-ε

## Properties

## Model equations

## Default model coefficients

## Initialisation

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        RNGkEpsilon;
}

```

## Boundary conditions

Walls

## Further information

Source code:

* [Foam::RASModels::RNGkEpsilon](https://api.openfoam.com/2606/Foam_RASModels_RNGkEpsilon.html)

References:

* *Yakhot et al.* [90](../../../../../../../references.md#yakhot_development_1992)
