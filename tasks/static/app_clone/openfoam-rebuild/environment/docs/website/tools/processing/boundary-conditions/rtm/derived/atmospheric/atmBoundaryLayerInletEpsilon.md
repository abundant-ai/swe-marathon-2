<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayerInletEpsilon -->

# atmBoundaryLayerInletEpsilon

## Description

The `atmBoundaryLayerInletEpsilon` is a boundary condition that provides
a log\-law type ground\-normal inlet boundary condition for the turbulent kinetic
energy dissipation rate (i.e. `epsilon`) for homogeneous, two\-dimensional,
dry\-air, equilibrium and neutral atmospheric boundary layer modelling.

The ground\-normal `epsilon` profile expression:

ϵ\=(u∗)3κ(z−d\+z0)C1ln⁡(z−d\+z0z0)\+C2 \\epsilon \= \\frac{(u^\*)^3}{\\kappa (z \- d \+ z\_0\)}
 \\sqrt{C\_1 \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right) \+ C\_2}ϵ\=κ(z−d\+z0​)(u∗)3​C1​ln(z0​z−d\+z0​​)\+C2​​
where:

| Property | Description |
| --- | --- |
| ϵ\\epsilonϵ | Ground\-normal TKE dissipation rate profile \[m^2/s^3] |
| u∗u^\*u∗ | Friction velocity \[m/s] |
| κ\\kappaκ | von Kármán constant \[\-] |
| zzz | Ground\-normal coordinate component \[m] |
| z0z\_0z0​ | Aerodynamic roughness length \[m] |
| ddd | Ground\-normal displacement height \[m] |
| C1C\_1C1​ | Curve\-fitting coefficient for YGCJ profiles \[\-] |
| C2C\_2C2​ | Curve\-fitting coefficient for YGCJ profiles \[\-] |

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
    type            atmBoundaryLayerInletEpsilon;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmBoundaryLayerInletEpsilon` | word | yes | \- |

The inherited entries are elaborated in:

* atmBoundaryLayer.H
* inletOutletFvPatchField.H

## Further information

Tutorial:

* [turbineSiting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbineSiting)

Source code:

* [atmBoundaryLayerInletEpsilon](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmBoundaryLayerInletEpsilon)

API:

* [Foam::atmBoundaryLayerInletEpsilonFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmBoundaryLayerInletEpsilonFvPatchScalarField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
