<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/ -->

# General conditions

## Boundary mesh type

General conditions are specified using the `patch` type entry in the
`$FOAM_CASE/constant/polyMesh/boundary` file:

```
<patchName>
{
    type            patch;
    ...
}

```

## Base types

Boundaries reduce to one of the following types:

* [Dirichlet](fixedValue.md): fixed value
* [Neumann](fixedGradient.md): fixed gradient
* [Mixed](mixed.md): linear combination of
Dirichlet and Neumann

## Options

Available general conditions include

* [codedFixedValue](codedFixedValue.md)
* [codedMixed](codedMixed.md)
* [copiedFixedValue](copiedFixedValue.md)
* [electrostaticDeposition](electrostaticDeposition.md)
* [Fixed gradient](fixedGradient.md)
* [fixedInternalValue](fixedInternalValue.md)
* [fixedNormalSlip](../wall/fixedNormalSlip.md)
* [fixedProfile](fixedProfile.md)
* [fixedValue](fixedValue.md)
* [interfaceCompression](interfaceCompression.md)
* [mappedField](mappedField.md)
* [mappedFixedInternalValue](mappedFixedInternalValue.md)
* [mappedFixedPushedInternalValue](mappedFixedPushedInternalValue.md)
* [mappedFixedValue](mappedFixedValue.md)
* [mappedMixed](mappedMixed.md)
* [Mixed](mixed.md)
* [prghPressure](prghPressure.md)
* [prghTotalHydrostaticPressure](prghTotalHydrostaticPressure.md)
* [prghTotalPressure](prghTotalPressure.md)
* [scaledFixedValue](scaledFixedValue.md)
* [solidBodyMotionDisplacement](solidBodyMotionDisplacement.md)
* [surfaceNormalFixedValue](surfaceNormalFixedValue.md)
* [uniformDensityHydrostaticPressure](uniformDensityHydrostaticPressure.md)
* [uniformFixedGradient](uniformFixedGradient.md)
* [uniformFixedValue](uniformFixedValue.md)
* [uniformMixed](uniformMixed.md)
* [variableHeightFlowRate](variableHeightFlowRate.md)
* [waveSurfacePressure](waveSurfacePressure.md)
* [Zero gradient](zeroGradient.md)

## Further information

Source code:

* [Foam::polyPatch](https://api.openfoam.com/2606/Foam_polyPatch.html)
* [Foam::fvPatch](https://api.openfoam.com/2606/Foam_fvPatch.html)

See also

* [grpGenericBoundaryConditions](https://api.openfoam.com/2606/grpGenericBoundaryConditions.html)
