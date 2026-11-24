<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/regular/rtm/stokesI -->

# Stokes I

## Properties

* Regular waves

## Model equations

The wave height is modelled by the equation:

η\=H2cos⁡(kx−ωt\+ϕ) \\eta \= \\frac{H}{2} \\cos (k x \-\\omega t \+ \\phi)η\=2H​cos(kx−ωt\+ϕ)
Where:

HHH
: wave height

kkk
: wave number

ω\\omegaω
: angular frequency

ϕ\\phiϕ
: phase shift

ttt
: time

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       StokesI;
    nPaddle         1;
    waveHeight      0.05;
    waveAngle       0.0;
    rampTime        3.0;
    activeAbsorption yes;
    wavePeriod      3.0;
}

```

## Further information

Source code:

* [Foam::waveModels::StokesI](https://api.openfoam.com/2606/Foam_waveModels_StokesI.html)

References:

* ...

Tutorials:

* [stokesI](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesI)
