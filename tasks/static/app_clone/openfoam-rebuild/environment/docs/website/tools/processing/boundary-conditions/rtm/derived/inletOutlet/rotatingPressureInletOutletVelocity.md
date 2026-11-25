<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/rotatingPressureInletOutletVelocity -->

# rotatingPressureInletOutletVelocity

## Description

The `rotatingPressureInletOutletVelocity` is a velocity inlet/outlet boundary
condition that applies a zero\-gradient condition for outflow (as defined by
the flux); and obtains velocity from the flux with a direction normal to
the patch faces. The condition is applied to patches in a rotating frame
where the pressure is specified.

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
    type            rotatingPressureInletOutletVelocity;
    omega           <Function1<vector>>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `rotatingPressureInletOutletVelocity` | word | yes | \- |
| `oemga` | Angular velocity of the frame \[rad/s] | Function1\<vector\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::pressureInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressureInletOutletVelocityFvPatchVectorField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

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

* [rotatingPressureInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/rotatingPressureInletOutletVelocity)

API:

* [Foam::rotatingPressureInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_rotatingPressureInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
