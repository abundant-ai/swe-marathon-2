<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/solitary/rtm/McCowan -->

# McCowan

## Properties

* Solitary wave

## Model equations

The wave height is modelled by the equation:

η\=atan⁡(0\.5m(a\+h))sin⁡(mz)cos⁡(mz)\+cosh⁡(mx) \\eta \=
 \\frac{a}{\\tan (0\.5 m (a \+ h))}
 \\frac{\\sin (m z)}{\\cos (m z) \+ \\cosh (m x) }η\=tan(0\.5m(a\+h))a​cos(mz)\+cosh(mx)sin(mz)​
Where:

hhh
: water depth

aaa
: wave amplitude

mmm
: constant coefficient

## Default model coefficients

## Usage

Inlet patch example

```
<patch>
{
    alpha           alpha.water;
    waveModel       McCowan;
    nPaddle         1;
    waveHeight      0.05;
    waveAngle       0.0;
    activeAbsorption yes;
}

```

## Further information

Source code:

* [Foam::waveModels::McCowan](https://api.openfoam.com/2606/Foam_waveModels_McCowan.html)

References:

* ...

Tutorials:

* [solitaryMcCowan](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/solitaryMcCowan)
