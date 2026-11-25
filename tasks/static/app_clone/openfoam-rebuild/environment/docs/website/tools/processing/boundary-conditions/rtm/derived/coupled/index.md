<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/ -->

# Coupled conditions

## Boundary mesh type

Coupled conditions require the `type` entry to be set in the
`$FOAM_CASE/constant/polyMesh/boundary` file, e.g.:

```
<patchName>
{
    type            <couple type>;
    ...
}

```

This is explained in further detail in the documentation for each coupled
boundary type.

## Coupled conditions

Available coupled conditions include

* [activeBaffleVelocity](../inlet/activeBaffleVelocity.md)
* [activePressureForceBaffleVelocity](../inlet/activePressureForceBaffleVelocity.md)
* [Cyclic](cyclic.md)
* [Cyclic Arbitrary Mesh Interface (AMI)](cyclicAMI.md)
* [swirlFanVelocity](swirlFanVelocity.md)
* [fan](fan.md)
* [fixedJump](fixedJump.md)
* [fixedJumpAMI](fixedJumpAMI.md)
* [humidityTemperatureCoupledMixed](humidityTemperatureCoupledMixed.md)
* [uniformJump](uniformJump.md)
* [uniformJumpAMI](uniformJumpAMI.md)

## Further information

Source code:

* [Foam::coupledPolyPatch](https://api.openfoam.com/2606/Foam_coupledPolyPatch.html)
* [Foam::coupledFvPatch](https://api.openfoam.com/2606/Foam_coupledFvPatch.html)

See also

* [grpCoupledBoundaryConditions](https://api.openfoam.com/2606/grpCoupledBoundaryConditions.html)
