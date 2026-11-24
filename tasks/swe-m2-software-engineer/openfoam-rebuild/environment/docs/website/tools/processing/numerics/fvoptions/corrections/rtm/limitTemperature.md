<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/corrections/rtm/limitTemperature -->

# Limit temperature

## Properties

* limits the temperature to user supplied minimum and maximum values

## Usage

```
limitT
{
    type            limitTemperature;
    active          yes;

    selectionMode   all;
    min             200;
    max             500;
    phase           gas; // optional
}

```

## Further information

Tutorials

* *none*

Source code

* [limitTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/corrections/limitTemperature)
