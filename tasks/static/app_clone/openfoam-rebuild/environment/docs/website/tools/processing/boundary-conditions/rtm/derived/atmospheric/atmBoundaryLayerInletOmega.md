<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayerInletOmega -->

# atmBoundaryLayerInletOmega

## Description

The `atmBoundaryLayerInletOmega` is a boundary condition that provides
boundary condition for the specific dissipation rate (i.e. `omega`)
for homogeneous, two\-dimensional, dry\-air, equilibrium and neutral
atmospheric boundary layer modelling.

The ground\-normal `omega` profile expression:

ω\=u∗κCμ1z−d\+z0 \\omega \= \\frac{u^\*}{\\kappa \\sqrt{C\_\\mu}} \\frac{1}{z \- d \+ z\_0}ω\=κCμ​​u∗​z−d\+z0​1​
where:

| Property | Description |
| --- | --- |
| ω\\omegaω | Ground\-normal specific dissipation rate profile \[m^2/s^3] |
| u∗u^\*u∗ | Friction velocity \[m/s] |
| κ\\kappaκ | von Karman constant \[\-] |
| CμC\_\\muCμ​ | Empirical model constant \[\-] |
| zzz | Ground\-normal coordinate component \[m] |
| ddd | Ground\-normal displacement height \[m] |
| z0z\_0z0​ | Aerodynamic roughness length \[m] |

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
    type            atmBoundaryLayerInletOmega;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmBoundaryLayerInletOmega` | word | yes | \- |

The inherited entries are elaborated in:

* atmBoundaryLayer.H
* inletOutletFvPatchField.H

## Further information

Tutorial:

* [atmDownstreamDevelopment](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmDownstreamDevelopment)

Source code:

* [atmBoundaryLayerInletOmega](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmBoundaryLayerInletOmega)

API:

* [Foam::atmBoundaryLayerInletOmegaFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmBoundaryLayerInletOmegaFvPatchScalarField.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
