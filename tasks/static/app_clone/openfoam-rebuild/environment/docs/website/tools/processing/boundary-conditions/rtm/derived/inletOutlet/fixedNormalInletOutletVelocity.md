<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/fixedNormalInletOutletVelocity -->

# fixedNormalInletOutletVelocity

## Description

The `fixedNormalInletOutletVelocity` is a velocity boundary condition that
combines a fixed normal component obtained from the `normalVelocity`
patch field supplied with a fixed or zero\-gradiented tangential component.

The tangential component is set depending on the direction
of the flow and the setting of `fixTangentialInflow` keyword:

* Outflow: apply zero\-gradient condition to tangential components.
* Inflow:

```
- `fixTangentialInflow` is true: apply value provided by the `normalVelocity`
patch field to the tangential components,
- `fixTangentialInflow` is false: apply zero-gradient condition to
tangential components.

```

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
    type                    fixedNormalInletOutletVelocity;
    fixTangentialInflow     <bool>;
    normalVelocity          <fvPatchVectorField>;

    //
    // normalVelocity
    // {
    //     type            uniformFixedValue;
    //     uniformValue    sine;
    //     uniformValueCoeffs
    //     {
    //         frequency 1;
    //         amplitude table
    //         (
    //             (0  0)
    //             (2  0.088)
    //             (8  0.088)
    //         );
    //         scale     (0 1 0);
    //         level     (0 0 0);
    //     }
    // }

    // Optional entries
    phi             <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedNormalInletOutletVelocity` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `fixTangentialInflow` | Flag to fix the tangential component for inflow | bool | yes | \- |
| `normalVelocity` | Boundary condition that provides the normal component of the velocity | fvPatchVectorField | yes | \- |

The inherited entries are elaborated in:

* [Foam::fvPatchField](https://api.openfoam.com/2606/Foam_fvPatchField.html)
* [Foam::directionMixedFvPatchField](https://api.openfoam.com/2606/Foam_directionMixedFvPatchField.html)

## Further information

Tutorial:

* [oscillatingBox](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/potentialFreeSurfaceFoam/oscillatingBox)

Source code:

* [fixedNormalInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedNormalInletOutletVelocity)

API:

* [Foam::fixedNormalInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_fixedNormalInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.3\.1](https://www.openfoam.com/news/main-news/openfoam-2.3.1)
