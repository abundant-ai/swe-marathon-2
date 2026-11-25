<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/pressureInletOutletVelocity -->

# Pressure inlet outlet velocity

## Properties

* Wrapper around the [mixed](../general/mixed.md) condition
* Applicable to the velocity vector field
* Flow out of the domain: assigns a
[zeroGradient](../general/zeroGradient.md) condition
* Flow into the domain: assigns a velocity based on the flux in the patch\-normal
direction

## Usage

The condition is specified in the field file using:

```
<patchName>
{
    type                pressureInletOutletVelocity;
    tangentialVelocity  <field value>;
    value               <field value>;

    // Optional entries
    phi                 phi;
}

```

## Further information

Source code:

* [Foam::pressureInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletOutletVelocityFvPatchVectorField.html)
