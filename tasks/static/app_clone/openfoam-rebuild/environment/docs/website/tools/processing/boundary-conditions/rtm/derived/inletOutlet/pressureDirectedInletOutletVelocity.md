<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/pressureDirectedInletOutletVelocity -->

# pressureDirectedInletOutletVelocity

## Description

The `pressureDirectedInletOutletVelocity` is a velocity inlet/outlet boundary
condition that applies zero\-gradient condition for outflow (as defined by the
flux); and obtains the velocity from the flux with the specified inlet direction
for inflow.

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
    type            pressureDirectedInletOutletVelocity;
    inletDirection  <vectorField>;

    // Optional entries
    phi             <word>;
    rho             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressureDirectedInletOutletVelocity` | word | yes | \- |
| `inletDirection` | Inlet direction field | vectorField | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [Foam::fvPatchField](https://api.openfoam.com/2606/Foam_fvPatchField.html)
* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

* Sign conventions:
	+ positive flux (out of domain): apply zero\-gradient condition
	+ negative flux (into of domain): derive from the flux with specified

```
direction

```

## Further information

Tutorial:

* N/A

Source code:

* [pressureDirectedInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureDirectedInletOutletVelocity)

API:

* [Foam::pressureDirectedInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureDirectedInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
