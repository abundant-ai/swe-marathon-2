<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall -->

# Wall conditions

## Boundary mesh type

Wall conditions are specified using the `wall` type entry in the
`$FOAM_CASE/constant/polyMesh/boundary` file:

```
patchName
{
    type            wall;
    ...
}

```

## Velocity

Available wall conditions include

* [fixedNormalSlip](wall/fixedNormalSlip.md)
* [movingWallVelocity](wall/movingWallVelocity.md)
* [noSlip](wall/noSlip.md)
* [partialSlip](wall/partialSlip.md)
* [rotatingWallVelocity](wall/rotatingWallVelocity.md)
* [SRFWallVelocity](wall/SRFWallVelocity.md)
* [translatingWallVelocity](wall/translatingWallVelocity.md)

## Pressure

* see [zeroGradient](general/zeroGradient.md)

## Temperature

* adiabatic: see [zero gradient](general/zeroGradient.md)
* fixed temperature: see [fixed value](general/fixedValue.md)
* fixed heat flux: see
[fixed gradient](general/fixedGradient.md)

## Turbulence

See turbulence wall modelling

* See [Reynolds Averaged Simulation](../../../models/turbulence/ras.md#wall-modelling)
* See [Detached Eddy Simulation](../../../models/turbulence/des.md#wall-modelling)
* See [Large Eddy Simulation](../../../models/turbulence/les.md#wall-modelling)

## Further information

Related:

* See [wall distance](../../../numerics/schemes/wall-distance/index.md)

Source code:

* [Foam::wallPolyPatch](https://api.openfoam.com/2606/Foam_wallPolyPatch.html)
* [Foam::wallFvPatch](https://api.openfoam.com/2606/Foam_wallFvPatch.html)

See also

* [grpWallBoundaryConditions](https://api.openfoam.com/2606/grpWallBoundaryConditions.html)
