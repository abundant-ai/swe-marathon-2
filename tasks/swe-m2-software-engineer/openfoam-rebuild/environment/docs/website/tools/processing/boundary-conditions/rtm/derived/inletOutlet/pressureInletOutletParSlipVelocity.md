<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/pressureInletOutletParSlipVelocity -->

# pressureInletOutletParSlipVelocity

## Description

The `pressureInletOutletParSlipVelocity` is a velocity inlet/outlet boundary
condition that applies a zero\-gradient condition for outflow (as defined by
the flux); and obtains velocity from the flux with specified inlet direction.

The `slip` condition is applied tangential to the patch.

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
    type            pressureInletOutletParSlipVelocity;

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
| `type` | Type name: `pressureInletOutletParSlipVelocity` | word | yes | \- |
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

* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceDyMFoam/oscillatingBox)

Source code:

* [pressureInletOutletParSlipVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressureInletOutletParSlipVelocity)

API:

* [Foam::pressureInletOutletParSlipVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletOutletParSlipVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
