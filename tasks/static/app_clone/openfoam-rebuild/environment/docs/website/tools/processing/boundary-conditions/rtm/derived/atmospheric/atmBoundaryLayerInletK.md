<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/atmospheric/atmBoundaryLayerInletK -->

# atmBoundaryLayerInletK

## Description

The `atmBoundaryLayerInletK` is a boundary condition that provides
boundary condition for the turbulent kinetic energy (i.e. `k`)
for homogeneous, two\-dimensional, dry\-air, equilibrium and neutral
atmospheric boundary layer modelling.

The ground\-normal `k` profile expression:

k\=(u∗)2CμC1ln⁡(z−d\+z0z0)\+C2 k \= \\frac{(u^\*)^2}{\\sqrt{C\_\\mu}}
 \\sqrt{C\_1 \\ln \\left( \\frac{z \- d \+ z\_0}{z\_0} \\right) \+ C\_2}k\=Cμ​​(u∗)2​C1​ln(z0​z−d\+z0​​)\+C2​​
where:

| Property | Description |
| --- | --- |
| kkk | Ground\-normal turbulent kinetic energy profile \[m^2/s^3] |
| u∗u^\*u∗ | Friction velocity \[m/s] |
| CμC\_\\muCμ​ | Empirical model constant \[\-] |
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
    type            atmBoundaryLayerInletK;

    // Inherited entries
    ...
    flowDir         (1 0 0);    // not used
    zDir            (0 0 1);    // not used
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `atmBoundaryLayerInletK` | word | yes | \- |

The inherited entries are elaborated in:

* atmBoundaryLayer.H
* inletOutletFvPatchField.H

## Further information

Tutorial:

* [turbineSiting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbineSiting)

Source code:

* [atmBoundaryLayerInletK](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/derivedFvPatchFields/atmBoundaryLayerInletK)

API:

* [Foam::atmBoundaryLayerInletKFvPatchScalarField](https://api.openfoam.com/2606/Foam_atmBoundaryLayerInletKFvPatchScalarField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
