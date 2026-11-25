<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/regular/rtm/stokesII -->

# Stokes II

## Properties

* Regular waves

## Model equations

The wave height is modelled by the equation:

η\=H2cos⁡(kx−ωt\+ϕ)\+kH243−σ24σ3cos⁡(2(kx−ωt\+ϕ)) \\eta \=
 \\frac{H}{2} \\cos (k x \-\\omega t \+ \\phi)
 \+ k \\frac{H^2}{4} \\frac{3 \- \\sigma^2}{4 \\sigma^3} \\cos \\left(2(k x \- \\omega t \+ \\phi)\\right)η\=2H​cos(kx−ωt\+ϕ)\+k4H2​4σ33−σ2​cos(2(kx−ωt\+ϕ))
Where:

HHH
: wave height

kkk
: wave number

ω\\omegaω
: angular frequency

σ\\sigmaσ
: radian wave frequency

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
    waveModel       StokesII;
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

* [Foam::waveModels::StokesII](https://api.openfoam.com/2606/Foam_waveModels_StokesII.html)

References:

* ...

Tutorials:

* [stokesII](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesII)
