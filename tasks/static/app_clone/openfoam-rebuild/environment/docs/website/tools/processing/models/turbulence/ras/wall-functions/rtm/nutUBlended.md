<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/wall-functions/rtm/nutUBlended -->

# Blended turbulence viscosity

## Properties

* Continuous wall function that blends contributions from the viscous sub\-layer
and logarithmic regions

uτ\=(uτ,sub4\+uτ,log4)0\.25 u\_\\tau \= \\left(u\_{\\tau,sub}^4 \+ u\_{\\tau,log}^4 \\right)^{0\.25}uτ​\=(uτ,sub4​\+uτ,log4​)0\.25
## Usage

The wall function is specified using:

```
wallPatch
{
    type            nutUBlendedWallFunction;
    value           XXX;
}

```

## Further information

Source code:

* [Foam::nutUBlendedWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutUBlendedWallFunctionFvPatchScalarField.html)

References:

* Automatic wall treatment: *Menter and Esch* [48](../../../../../../../references.md#menter_elements_2001)
