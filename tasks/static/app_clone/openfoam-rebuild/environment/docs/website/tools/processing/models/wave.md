<!-- https://doc.openfoam.com/2606/tools/processing/models/wave -->

# Wave

## Solitary wave theories

* [Boussinesq](wave-models/solitary/rtm/Boussinesq.md)
* [Grimshaw](wave-models/solitary/rtm/Grimshaw.md)
* [McCowan](wave-models/solitary/rtm/McCowan.md)

## Regular wave theories

* [Cnoidal](wave-models/regular/rtm/cnoidal.md)
* [Stokes I](wave-models/regular/rtm/stokesI.md)
* [Stokes II](wave-models/regular/rtm/stokesII.md)
* [Stokes V](wave-models/regular/rtm/stokesV.md)
* [Stream function](wave-models/regular/rtm/streamFunction.md)

## Wave absorption theories

* [Shallow water Absorption](wave-models/absorption/rtm/shallowWaterAbsorption.md)

## Usage

Wave cases are set\-up by defining
[boundary conditions](../boundary-conditions.md)
on the velocity and phase fraction fields, in combination with common settings
in the `waveProperties` dictionary located in the `constant` directory.

The condition on the phase fraction field, typically named `alpha`, is set to
`waveAlpha`:

```
<patch>
{
    type            waveAlpha;
    values          <initial value>;
}

```

and the velocity field, typically named `U`, to `waveVelocity`:

```
<patch>
{
    type            waveVelocity;
    values          <initial value>;
}

```

## Further information

Source code:

* [waveModels](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/waveModels)
