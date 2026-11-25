<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/regular/rtm/stokesV -->

# Stokes V

## Properties

* Regular waves

## Model equations

The wave height is modelled by the equation:

η\=λkcos⁡(kx−ωt\+ϕ)\+(λ2B22\+λ4B24)λcos⁡(2(kx−ωt\+ϕ))\+(λ3B33\+λ5B35)λcos⁡(3(kx−ωt\+ϕ))\+(λ4B44)λcos⁡(4(kx−ωt\+ϕ))\+(λ5B55)λcos⁡(5(kx−ωt\+ϕ)) \\eta \=
 \\frac{\\lambda}{k} \\cos (k x \-\\omega t \+ \\phi)
 \+ \\frac{(\\lambda^2 B\_{22} \+ \\lambda^4 B\_{24})}{\\lambda}
 \\cos\\left(2(k x \- \\omega t \+ \\phi)\\right)
 \+ \\frac{(\\lambda^3 B\_{33} \+ \\lambda^5 B\_{35})}{\\lambda}
 \\cos\\left(3(k x \- \\omega t \+ \\phi)\\right)
 \+ \\frac{(\\lambda^4 B\_{44})}{\\lambda}
 \\cos\\left(4(k x \- \\omega t \+ \\phi)\\right)
 \+ \\frac{(\\lambda^5 B\_{55})}{\\lambda}
 \\cos\\left(5(k x \- \\omega t \+ \\phi)\\right)η\=kλ​cos(kx−ωt\+ϕ)\+λ(λ2B22​\+λ4B24​)​cos(2(kx−ωt\+ϕ))\+λ(λ3B33​\+λ5B35​)​cos(3(kx−ωt\+ϕ))\+λ(λ4B44​)​cos(4(kx−ωt\+ϕ))\+λ(λ5B55​)​cos(5(kx−ωt\+ϕ))
Where:

λ\\lambdaλ
: first order wave amplitude

kkk
: wave number

ω\\omegaω
: angular frequency

ϕ\\phiϕ
: phase shift

BxxB\_{xx}Bxx​
: coefficients in the fifth order solution

ttt
: time

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       StokesV;
    nPaddle         1;
    waveHeight      0.1;
    waveAngle       0.0;
    rampTime        4.0;
    activeAbsorption yes;
    wavePeriod      2.0;
}

```

## Further information

Source code:

* [Foam::waveModels::StokesV](https://api.openfoam.com/2606/Foam_waveModels_StokesV.html)

References:

* ...

Tutorials:

* [stokesV](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/stokesV)
