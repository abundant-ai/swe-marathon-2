<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/turbulentIntensityKineticEnergyInlet -->

# Turbulent intensity kinetic energy

## Properties

* based on the [inlet\-outlet](../inletOutlet/inletOutlet.md)
condition
* sets the turbulent kinetic energy based on the patch velocity and
user\-supplied turbulence intensity

kp\=1\.5(I∣u∣)2 k\_p \= 1\.5 \\left( I \\mag{\\u} \\right)^2kp​\=1\.5(I∣u∣)2
* in the event of reverse flow, a
[zeroGradient](../general/zeroGradient.md) condition is
applied, i.e.

dkdx\=0 \\frac{d k}{d x} \= 0dxdk​\=0
## Usage

The condition is specified in the field file using:

```
<patchName>
{
    type        turbulentIntensityKineticEnergyInlet;
    intensity   0.05;
    value       <field value>;

    // Optional entries
    U           U;
    phi         phi;
}

```

## Further information

Source code:

* [Foam::turbulentIntensityKineticEnergyInletFvPatchScalarField](https://api.openfoam.com/2606/Foam_turbulentIntensityKineticEnergyInletFvPatchScalarField.html)
