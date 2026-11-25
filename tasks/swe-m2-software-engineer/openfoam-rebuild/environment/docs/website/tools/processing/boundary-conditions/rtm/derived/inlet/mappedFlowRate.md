<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/mappedFlowRate -->

# mappedFlowRate

## Description

The `mappedFlowRate` is a velocity boundary condition that describes a
volumetric/mass flow normal vector boundary condition by its magnitude
as an integral over its area.

The inlet mass flux is taken from the neighbour region.

The basis of the patch (volumetric or mass) is determined by the
dimensions of the flux, `phi`. The current density is used to correct the
velocity when applying the mass basis.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            mappedPatch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                mappedFlowRate;

    // Optional entries
    nbrPhi              <word>;
    phi                 <word>;
    rho                 <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedFlowRate` | word | yes | \- |
| `nbrPhi` | Name of the neighbour flux setting the inlet mass flux | word | no | phi |
| `phi` | Name of the local mass flux | word | no | phi |
| `rho` | Name of the density field used to normalize the mass flux | word | no | rho |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [flameSpreadWaterSuppressionPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/flameSpreadWaterSuppressionPanel)
* [oppositeBurningPanels](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/oppositeBurningPanels)

Source code:

* [mappedFlowRate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedFlowRate)

API:

* [Foam::mappedFlowRateFvPatchVectorField](https://api.openfoam.com/2606/Foam_mappedFlowRateFvPatchVectorField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
