<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/pressureInletOutletVelocity -->

# pressureInletOutletVelocity

## Description

The `pressureInletOutletVelocity` is a velocity inlet/outlet boundary
condition that applies a zero\-gradient condition for outflow (as defined by
the flux); and obtains velocity from the flux with specified inlet direction.

The tangential patch velocity can be optionally specified.

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
    type            pressureInletOutletVelocity;

    // Optional entries
    tangentialVelocity  <vectorField>;
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressureInletOutletVelocity` | word | yes | \- |
| `tangentialVelocity` | Tangential velocity field | vectorField | no | Zero |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [Foam::directionMixedFvPatchField](https://api.openfoam.com/2606/Foam_directionMixedFvPatchField.html)

* Sign conventions:
	+ positive flux (out of domain): apply zero\-gradient condition
	+ negative flux (into of domain): derive from the flux with specified

```
direction

```

## Further information

Tutorial:

* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunction)

Source code:

* [pressureInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureInletOutletVelocity)

API:

* [Foam::pressureInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
