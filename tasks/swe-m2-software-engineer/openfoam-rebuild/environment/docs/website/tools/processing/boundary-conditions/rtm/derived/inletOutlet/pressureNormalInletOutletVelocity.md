<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/pressureNormalInletOutletVelocity -->

# pressureNormalInletOutletVelocity

## Description

The `pressureNormalInletOutletVelocity` is a velocity inlet/outlet boundary
condition that applies a zero\-gradient condition for outflow (as defined by
the flux); and obtains velocity from the flux with a direction normal
to the patch faces.

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
    type            pressureNormalInletOutletVelocity;

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
| `type` | Type name: `pressureNormalInletOutletVelocity` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |

The inherited entries are elaborated in:

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

* [pressureNormalInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureNormalInletOutletVelocity)

API:

* [Foam::pressureNormalInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureNormalInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
