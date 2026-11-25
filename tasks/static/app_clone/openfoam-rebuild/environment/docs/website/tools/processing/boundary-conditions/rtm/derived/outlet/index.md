<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/ -->

# Outlet conditions

## Boundary mesh type

Outlet conditions are specified using the `patch` type entry in the
`$FOAM_CASE/constant/polyMesh/boundary` file:

```
<patchName>
{
    type            patch;
    ...
}

```

## General conditions

Available outlet conditions include

* [acousticWaveTransmissive](acousticWaveTransmissive.md)
* [advective](advective.md)
* [fluxCorrectedVelocity](fluxCorrectedVelocity.md)
* [Inlet outlet](inletOutlet.md)
* [waveTransmissive](waveTransmissive.md)

## Velocity conditions

* blocked return flow: see [inlet outlet](../inletOutlet/inletOutlet.md)
* outflow: see [zeroGradient](../general/zeroGradient.md). Note:
unstable for reverse flow

* [matchedFlowRateOutletVelocity](matchedFlowRateOutletVelocity.md)
* [outletPhaseMeanVelocity](outletPhaseMeanVelocity.md)
* [Pressure inlet outlet velocity](pressureInletOutletVelocity.md)

## Pressure conditions

* static pressure: see [fixedValue](../general/fixedGradient.md)

* *None*
