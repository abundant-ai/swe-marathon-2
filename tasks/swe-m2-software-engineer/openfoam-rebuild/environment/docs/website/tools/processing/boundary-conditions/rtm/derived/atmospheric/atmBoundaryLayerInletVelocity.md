<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayerInletVelocity -->

# atmBoundaryLayerInletVelocity

## Description

The `atmBoundaryLayerInletVelocity` is a boundary condition that provides
a log\-law type ground\-normal inlet boundary condition for the streamwise
component of wind velocity (i.e. `u`) for homogeneous, two\-dimensional,
dry\-air, equilibrium and neutral atmospheric boundary layer modelling.

The ground\-normal streamwise flow speed profile expression:

u\=u∗κln⁡(z−d\+z0z0) u \= \\frac{u^\*}{\\kappa} \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right)u\=κu∗​ln(z0​z−d\+z0​​)
v\=w\=0 v \= w \= 0v\=w\=0
where:

| Property | Description |
| --- | --- |
| uuu | Ground\-normal streamwise flow speed profile \[m/s] |
| vvv | Spanwise flow speed \[m/s] |
| www | Ground\-normal flow speed \[m/s] |
| u∗u^\*u∗ | Friction velocity \[m/s] |
| κ\\kappaκ | von Kármán constant \[\-] |
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
    type            atmBoundaryLayerInletVelocity;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmBoundaryLayerInletVelocity` | word | yes | \- |

The inherited entries are elaborated in:

* atmBoundaryLayer.H
* inletOutletFvPatchField.H

## Further information

Tutorial:

* [turbineSiting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbineSiting)

Source code:

* [atmBoundaryLayerInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmBoundaryLayerInletVelocity)

API:

* [Foam::atmBoundaryLayerInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_atmBoundaryLayerInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
