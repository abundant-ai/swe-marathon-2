<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/regular/rtm/cnoidal -->

# Cnoidal

## Properties

* Regular waves

## Model equations

The wave height is modelled by the equation:

η\=H\[1m(1−E(m)K(m))−1\+cn2(2K(m)x−ctλ)] \\eta \= H
 \\left\[
 \\frac{1}{m} \\left( 1 \- \\frac{E(m)}{K(m)} \\right)
 \- 1
 \+ cn^2\\left( 2 K(m) \\frac{x \- ct}{\\lambda} \\right)
 \\right]η\=H\[m1​(1−K(m)E(m)​)−1\+cn2(2K(m)λx−ct​)]
Where:

λ\\lambdaλ
: wavelength

mmm
: elliptic parameter that depends on the wave characteristic

K(m)K(m)K(m)
: complete elliptic integral of the first kind

E(m)E(m)E(m)
: complete elliptic integral of the second kind

cncncn
: Jacobi's elliptic functions

ccc
: wave celerity

HHH
: wave height

ttt
: time

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       cnoidal;
    nPaddle         1;
    waveHeight      0.1;
    waveAngle       0.0;
    rampTime        6.0;
    activeAbsorption yes;
    wavePeriod      4.0;
}

```

## Further information

Source code:

* [Foam::waveModels::cnoidal](https://api.openfoam.com/2606/Foam_waveModels_cnoidal.html)

References:

* ...

Tutorials:

* [cnoidal](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/cnoidal)
