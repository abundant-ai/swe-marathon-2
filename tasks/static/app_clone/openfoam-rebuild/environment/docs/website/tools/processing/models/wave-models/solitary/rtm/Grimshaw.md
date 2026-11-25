<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/solitary/rtm/Grimshaw -->

# Grimshaw

## Properties

* Solitary wave

## Model equations

The wave height is modelled by the equation:

η\=1\+ϵs2\+34ϵ2s2t2\+ϵ3(58s2t2−10180s4t2) \\eta \=
 1
 \+ \\epsilon s^2
 \+ \\frac{3}{4} \\epsilon^2 s^2 t^2
 \+ \\epsilon^3 \\left( \\frac{5}{8} s^2 t^2 \- \\frac{101}{80} s^4 t^2\\right)η\=1\+ϵs2\+43​ϵ2s2t2\+ϵ3(85​s2t2−80101​s4t2)
and

ϵ\=ah;s\=sech(αx);t\=tanh⁡(αx);α\=34ϵ(1−58ϵ\+71128ϵ2) \\epsilon \= \\frac{a}{h}; s \= \\mathrm{sech} (\\alpha x); t \= \\tanh(\\alpha x);
 \\alpha \= \\sqrt{\\frac{3}{4} \\epsilon} \\left( 1 \- \\frac{5}{8} \\epsilon \+ \\frac{71}{128}\\epsilon^2 \\right)ϵ\=ha​;s\=sech(αx);t\=tanh(αx);α\=43​ϵ​(1−85​ϵ\+12871​ϵ2)
Where:

hhh
: water depth

aaa
: wave amplitude

ttt
: time

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       Grimshaw;
    nPaddle         1;
    waveHeight      0.05;
    waveAngle       0.0;
    activeAbsorption no;
}

```

## Further information

Source code:

* [Foam::waveModels::Grimshaw](https://api.openfoam.com/2606/Foam_waveModels_Grimshaw.html)

References:

* ...

Tutorials:

* [solitaryGrimshaw](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/solitaryGrimshaw)
