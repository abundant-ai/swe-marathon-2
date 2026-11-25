<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/interstitialInletVelocity -->

# interstitialInletVelocity

## Description

The `interstitialInletVelocity` is a velocity boundary condition with which
the actual interstitial velocity is calculated by dividing the specified
`inletVelocity` field with the local phase\-fraction.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                interstitialInletVelocity;
    inletVelocity       <vectorField>;
    alpha               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `interstitialInletVelocity` | word | yes | \- |
| `inletVelocity` | Non\-interstitial inlet velocity | vectorField | yes | \- |
| `alpha` | Name of the phase\-fraction field | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [Goldschmidt](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/DPMFoam/Goldschmidt)
* [fluidisedBed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/RAS/fluidisedBed)

Source code:

* [interstitialInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/interstitialInletVelocity)

API:

* [Foam::interstitialInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_interstitialInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
