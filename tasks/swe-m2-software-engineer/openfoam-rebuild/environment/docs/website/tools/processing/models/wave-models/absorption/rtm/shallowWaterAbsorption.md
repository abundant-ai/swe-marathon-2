<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/absorption/rtm/shallowWaterAbsorption -->

# Shallow water Absorption

## Properties

* Outlet condition

## Model equations

## Default model coefficients

## Usage

Outlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       shallowWaterAbsorption;
    nPaddle         1;
}

```

## Further information

Source code:

* [Foam::waveModels::shallowWaterAbsorption](https://api.openfoam.com/2606/Foam_waveModels_shallowWaterAbsorption.html)

References:

* ...

Tutorials:

* [cnoidal](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/cnoidal)
* [stokesI](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesI)
* [stokesII](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesII)
* [stokesV](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesV)
