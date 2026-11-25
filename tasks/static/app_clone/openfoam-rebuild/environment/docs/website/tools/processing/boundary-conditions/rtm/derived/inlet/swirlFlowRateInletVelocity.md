<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/swirlFlowRateInletVelocity -->

# swirlFlowRateInletVelocity

## Description

The `swirlFlowRateInletVelocity` is a velocity boundary condition
that provides a volumetric\- or mass\-flow normal vector
boundary condition by its magnitude as an integral over its area with a
swirl component determined by the angular speed, given in revolutions per
minute (RPM).

The basis of the patch (volumetric or mass) is determined by the
dimensions of the flux, `phi`. The current density is used to correct the
velocity when applying the mass basis.

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
    type           swirlFlowRateInletVelocity;
    flowRate       <Function1<scalar>>;
    rpm            <Function1<scalar>>;

    // Optional entries
    phi            <word>;
    rho            <word>;
    origin         <vector>;
    axis           <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `swirlFlowRateInletVelocity` | word | yes | \- |
| `flowRate` | Flow rate profile | Function1\<scalar\> | yes | \- |
| `rpm` | Rotational speed profile | Function1\<scalar\> | yes | \- |
| `phi` | Name of the flux field | word | no | phi |
| `rho` | Name of the density field | word | no | rho |
| `origin` | Origin of rotation | vector | no | Zero |
| `axis` | Axis of rotation | vector | no | Zero |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* The value is positive into the domain.

## Further information

Tutorial:

* N/A

Source code:

* [swirlFlowRateInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/swirlFlowRateInletVelocity)

API:

* [Foam::swirlFlowRateInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_swirlFlowRateInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0)
