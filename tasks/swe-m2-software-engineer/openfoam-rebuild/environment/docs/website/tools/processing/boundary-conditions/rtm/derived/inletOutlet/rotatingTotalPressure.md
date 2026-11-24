<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/rotatingTotalPressure -->

# rotatingTotalPressure

## Description

The `rotatingTotalPressure` is a boundary condition that provides a total
pressure condition for patches in a rotating frame.

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
    type            rotatingTotalPressure;
    omega           <Function1<vector>>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `rotatingTotalPressure` | word | yes | \- |
| `oemga` | Angular velocity of the frame \[rad/s] | Function1\<vector\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::totalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_totalPressureFvPatchScalarField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* N/A

Source code:

* [rotatingTotalPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/rotatingTotalPressure)

API:

* [Foam::rotatingTotalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_rotatingTotalPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
