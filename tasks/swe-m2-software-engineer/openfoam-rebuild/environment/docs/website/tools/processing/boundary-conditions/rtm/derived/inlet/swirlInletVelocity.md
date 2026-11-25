<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/swirlInletVelocity -->

# swirlInletVelocity

## Description

The `swirlInletVelocity` is a velocity boundary condition
that describes an inlet vector boundary condition in swirl coordinates given a
central axis, central point, axial, radial and tangential velocity profiles.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type                patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                swirlInletVelocity;
    axialVelocity       <Function1<scalar>>;
    radialVelocity      <Function1<scalar>>;
    tangentialVelocity  <Function1<scalar>>;
    origin         <vector>;
    axis           <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `swirlInletVelocity` | word | yes | \- |
| `axialVelocity` | Axial\-velocity profile | Function1\<scalar\> | yes | \- |
| `radialVelocity` | Radial\-velocity profile | Function1\<scalar\> | yes | \- |
| `tangentialVelocity` | Tangential\-velocity profile | Function1\<scalar\> | yes | \- |
| `origin` | Origin of rotation | vector | no | Zero |
| `axis` | Axis of rotation | vector | no | Zero |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* N/A

Source code:

* [swirlInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/swirlInletVelocity)

API:

* [Foam::swirlInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_swirlInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
