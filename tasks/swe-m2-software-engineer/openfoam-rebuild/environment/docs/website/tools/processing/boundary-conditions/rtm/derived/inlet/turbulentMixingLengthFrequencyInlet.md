<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/turbulentMixingLengthFrequencyInlet -->

# Turbulent mixing length frequency

## Properties

* based on the [inlet\-outlet](../inletOutlet/inletOutlet.md)
condition
* sets the turbulent specific dissipation rate based on the patch turbulence
kinetic energy and user\-supplied mixing length

ωp\=k0\.5Cμ0\.25L \\omega\_p \= \\frac{k^{0\.5}}{C\_{\\mu}^{0\.25} L}ωp​\=Cμ0\.25​Lk0\.5​
* in the event of reverse flow, a
[zeroGradient](../general/zeroGradient.md) condition is
applied, i.e.

dωdx\=0 \\frac{d \\omega}{d x} \= 0dxdω​\=0
## Usage

The condition is specified in the field file using:

```
<patchName>
{
    type            turbulentMixingLengthFrequencyInlet;
    mixingLength    1;
    value           <field value>;

    // Optional entries
    omega           omega;
    phi             phi;
}

```

## Further information

Source code:

* [Foam::turbulentMixingLengthDissipationRateInletFvPatchScalarField](https://api.openfoam.com/2606/Foam_turbulentMixingLengthDissipationRateInletFvPatchScalarField.html)
