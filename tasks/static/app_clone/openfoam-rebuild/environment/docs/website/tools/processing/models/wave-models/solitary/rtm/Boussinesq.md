<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/solitary/rtm/Boussinesq -->

# Boussinesq

## Properties

* Solitary wave

## Model equations

The wave height is modelled by the equation:

η\=H\[sech34Hhx−cth]2 \\eta \= H \\left\[ \\mathrm{sech} \\sqrt{\\frac{3}{4} \\frac{H}{h} \\frac{x \- c t}{h}}\\right]^2η\=H\[sech43​hH​hx−ct​​]2
Where:

HHH
: wave height

hhh
: water depth

ccc
: wave celerity

ttt
: time

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       Boussinesq;
    nPaddle         1;
    waveHeight      0.3;
    waveAngle       0.0;
    activeAbsorption yes;
    wavePeriod      0.0;
}

```

## Further information

Source code:

* [Foam::waveModels::Boussinesq](https://api.openfoam.com/2606/Foam_waveModels_Boussinesq.html)

References:

* ...

Tutorials:

* [solitary](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/solitary)
