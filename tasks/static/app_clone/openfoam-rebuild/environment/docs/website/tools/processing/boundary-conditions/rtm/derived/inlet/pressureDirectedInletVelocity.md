<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/pressureDirectedInletVelocity -->

# pressureDirectedInletVelocity

## Description

The `pressureDirectedInletVelocity` is a velocity boundary condition that
calculates inflow velocity from the flux with the specified inlet
direction.

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
    type                pressureDirectedInletVelocity;
    inletDirection      <vectorField>;

    // Optional entries
    rho                 <word>;
    phi                 <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressureDirectedInletVelocity` | word | yes | \- |
| `inletDirection` | Inlet direction field | vectorField | yes | \- |
| `rho` | Name of the density field | word | no | rho |
| `phi` | Name of the flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

* If reverse flow is possible or expected use the
`pressureDirectedInletOutletVelocity` condition instead.

## Further information

Tutorial:

* N/A

Source code:

* [pressureDirectedInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureDirectedInletVelocity)

API:

* [Foam::pressureDirectedInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureDirectedInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
