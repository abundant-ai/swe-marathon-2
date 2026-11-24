<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/inletOutlet -->

# Inlet outlet

## Properties

* Wrapper around the [mixed](../general/mixed.md) condition
* Applicable to all variables
* Sets the patch value to a user\-specified
[fixedValue](../general/fixedGradient.md) for reverse flow
* Outflow treated using a
[zeroGradient](../general/zeroGradient.md) condition

## Usage

The condition is specified in the field file using:

```
<patchName>
{
    type            inletOutlet;
    inletValue      <field value>;
    value           <field value>;

    // Optional entries
    phi             phi;
}

```

## Further information

Source code:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)
* [Foam::zeroGradientFvPatchField](https://api.openfoam.com/2606/Foam_zeroGradientFvPatchField.html)
* [Foam::outletInletFvPatchField](https://api.openfoam.com/2606/Foam_outletInletFvPatchField.html)
