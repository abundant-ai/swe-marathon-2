<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/zeroGradient/ -->

# Zero gradient

## Properties

* Wrapper around the
[fixed gradient](../fixedGradient.md) condition
* Sets the field to the internal field value
* Applicable to all variable types

∂∂nϕ\=0 \\frac{\\partial}{\\partial n} \\phi \= 0∂n∂​ϕ\=0
## Usage

The condition is specified in the field file using:

```
<patchName>
{
    type            zeroGradient;
}

```

## Further information

Source code:

* [Foam::fixedGradientFvPatchField](https://api.openfoam.com/2606/Foam_fixedGradientFvPatchField.html)
* [Foam::zeroGradientFvPatchField](https://api.openfoam.com/2606/Foam_zeroGradientFvPatchField.html)
