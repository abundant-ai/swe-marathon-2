<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/matchedFlowRateOutletVelocity -->

# matchedFlowRateOutletVelocity

## Description

The `matchedFlowRateOutletVelocity` is a velocity\-outlet boundary condition that
corrects the extrapolated velocity to match the flow rate of the specified
corresponding inlet patch.

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
    type            matchedFlowRateOutletVelocity;

    // Optional entries
    inletPatch      <word>;
    rho             <word>;
    volumetric      <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `matchedFlowRateOutletVelocity` | word | yes | \- |
| `inletPatch` | Name of patch from which the corresponding flow rate is obtained | word | yes | \- |
| `rho` | Name of the density field used to normalize the mass flux | word | no | rho |
| `volumetric` | Flag to enable volumetric\- (true) of mass\-based flow rate | bool | no | true |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [matchedFlowRateOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/matchedFlowRateOutletVelocity)

API:

* [Foam::matchedFlowRateOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_matchedFlowRateOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
