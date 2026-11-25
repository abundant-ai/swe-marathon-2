<!-- https://doc.openfoam.com/2606/tools/processing/models/wave-models/regular/rtm/streamFunction -->

# Stream function

## Properties

* Regular waves

## Model equations

The wave height is modelled by the equation:

η\=h∑j\=1NEjcos⁡(j(kx−ωt\+ϕ)) \\eta \= h \\sum\\limits\_{j\=1}^N E\_j \\cos \\left( j (k x \- \\omega t \+ \\phi) \\right)η\=hj\=1∑N​Ej​cos(j(kx−ωt\+ϕ))
Where:

hhh
: water depth

EjE\_jEj​
: Fourrier coefficients of the computed free surface

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
    waveModel       streamFunction;
    nPaddle         1;
    waveHeight      0.1517;
    waveAngle       0.0;
    rampTime        6.034;
    activeAbsorption yes;
    wavePeriod      3.017;
    uMean           2.0825;
    waveLength      6.2832;

    Bjs
    (
        8.6669014e-002
        2.4849799e-002
        7.7446850e-003
        2.3355420e-003
        6.4497731e-004
        1.5205114e-004
        2.5433769e-005
       -2.2045436e-007
       -2.8711504e-006
       -1.2287334e-006
    );

    Ejs
    (
        5.6009609e-002
        3.1638171e-002
        1.5375952e-002
        7.1743178e-003
        3.3737077e-003
        1.6324880e-003
        8.2331980e-004
        4.4403497e-004
        2.7580059e-004
        2.2810557e-004
    );
}

```

## Further information

Source code:

* [Foam::waveModels::streamFunction](https://api.openfoam.com/2606/Foam_waveModels_streamFunction.html)

References:

* ...

Tutorials:

* [streamFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/waves/streamFunction)
