<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/ -->

# Inlet conditions

## Boundary mesh type

Inlet conditions are specified using the `patch` type entry in the
`$FOAM_CASE/constant/polyMesh/boundary` file:

```
<patchName>
{
    type            patch;
    ...
}

```

## General conditions

Available inlet conditions include

* [fixedMean](fixedMean.md)
* [outletInlet](outletInlet.md)
* [outletMappedUniformInlet](outletMappedUniformInlet.md)

## Velocity conditions

* fixed velocity: [fixedValue](../general/fixedGradient.md)

* [activeBaffleVelocity](activeBaffleVelocity.md)
* [activePressureForceBaffleVelocity](activePressureForceBaffleVelocity.md)
* [cylindricalInletVelocity](cylindricalInletVelocity.md)
* [flowRateInletVelocity](flowRateInletVelocity.md)
* [interstitialInletVelocity](interstitialInletVelocity.md)
* [mappedFlowRate](mappedFlowRate.md)
* [mappedVelocityFluxFixedValue](mappedVelocityFluxFixedValue.md)
* [pressureDirectedInletVelocity](pressureDirectedInletVelocity.md)
* [pressureInletUniformVelocity](pressureInletUniformVelocity.md)
* [pressureInletVelocity](pressureInletVelocity.md)
* [pressurePIDControlInletVelocity](pressurePIDControlInletVelocity.md)
* [swirlFlowRateInletVelocity](swirlFlowRateInletVelocity.md)
* [swirlInletVelocity](swirlInletVelocity.md)
* [syringePressure](syringePressure.md)
* [timeVaryingMappedFixedValue](../meshMotion/timeVaryingMappedFixedValue.md)
* [turbulentDFSEMInlet](turbulentDFSEMInlet.md)
* [turbulentDigitalFilterInlet](turbulentDigitalFilterInlet.md)
* [turbulentInlet](turbulentInlet.md)
* [uniformNormalFixedValue](uniformNormalFixedValue.md)
* [variableHeightFlowRateInletVelocity](variableHeightFlowRateInletVelocity.md)

## Pressure conditions

* fixed static pressure: see
[fixedValue](../general/fixedGradient.md)
* flow inlet: see [zeroGradient](../general/zeroGradient.md)

* [fixedFluxPressure](fixedFluxPressure.md)
* [fixedPressureCompressibleDensity](fixedPressureCompressibleDensity.md)
* [plenumPressure](plenumPressure.md)
* [uniformTotalPressure](uniformTotalPressure.md)

## Temperature conditions

* fixed temperature: [fixedValue](../general/fixedGradient.md)

## Turbulence conditions

* [Turbulent intensity kinetic energy](turbulentIntensityKineticEnergyInlet.md)
* *None*
* [Turbulent mixing length frequency](turbulentMixingLengthFrequencyInlet.md)

## Further information

Source code:

* [Foam::polyPatch](https://api.openfoam.com/2606/Foam_polyPatch.html)
* [Foam::fvPatch](https://api.openfoam.com/2606/Foam_fvPatch.html)

See also

* [grpInletBoundaryConditions](https://api.openfoam.com/2606/grpInletBoundaryConditions.html)
