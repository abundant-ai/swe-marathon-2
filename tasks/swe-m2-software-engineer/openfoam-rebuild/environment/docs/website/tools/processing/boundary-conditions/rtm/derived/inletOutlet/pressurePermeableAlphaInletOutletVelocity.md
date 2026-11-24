<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/pressurePermeableAlphaInletOutletVelocity -->

# pressurePermeableAlphaInletOutletVelocity

## Description

The `pressurePermeableAlphaInletOutletVelocity` is a velocity inlet/outlet boundary
condition that can be applied to velocity boundaries for multiphase flows when
the pressure boundary condition is specified.

In this condition , an open condition is applied when `alpha` is under a
user\-defined `alphaMin` value and a wall condition is applied when `alpha`
is larger than the `alphaMin`.

This boundary condition can be used in conjunction with
`prghPermeableAlphaTotalPressure` for the `p_rgh` variable.

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
    type            pressurePermeableAlphaInletOutletVelocity;

    // Optional entries
    phi             <word>;
    rho             <word>;
    alpha           <word>;
    alphaMin        <scalar>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressurePermeableAlphaInletOutletVelocity` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `alpha` | Name of the mixture VOF field | word | no | none |
| `alphaMin` | Minimum alpha value to outlet blockage | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [pressurePermeableAlphaInletOutletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressurePermeableAlphaInletOutletVelocity)

API:

* [Foam::pressurePermeableAlphaInletOutletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressurePermeableAlphaInletOutletVelocityFvPatchVectorField.html)

**History:** Introduced in version [v2106](https://www.openfoam.com/news/main-news/openfoam-v2106)
