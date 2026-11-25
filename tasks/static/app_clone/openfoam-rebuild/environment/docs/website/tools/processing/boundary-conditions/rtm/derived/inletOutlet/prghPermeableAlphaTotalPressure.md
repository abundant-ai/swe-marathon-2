<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/prghPermeableAlphaTotalPressure -->

# prghPermeableAlphaTotalPressure

## Description

The `prghPermeableAlphaTotalPressure` is a is a mixed boundary condition
for the `p_rgh` variable in multiphase flows.

It switches between an open boundary using the `prghTotalPressure`
boundary condition and a wall condition using the `fixedFluxPressure`
boundary condition.

In the `prghPermeableAlphaTotalPressure`, an open condition is
applied when `alpha` is under a user\-defined `alphaMin` value and a wall
condition is applied when `alpha` is larger than the `alphaMin`.

This boundary condition can be used in conjunction with
`pressurePermeableAlphaInletOutletVelocity` for the `U` variable.

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
    type            prghPermeableAlphaTotalPressure;
    p               <PatchFunction1<scalar>>;

    // Optional entries
    phi             <word>;
    rho             <word>;
    U               <word>;
    alpha           <word>;
    alphaMin        <scalar>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `prghPermeableAlphaTotalPressure` | word | yes | \- |
| `p` | Total pressure | PatchFunction1\<scalar\> | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `U` | Name of velocity field | word | no | U |
| `alpha` | Name of mixture field | word | no | alpha |
| `alphaMin` | Minimum value of alpha | scalar | no | 1 |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)
* [Foam::PatchFunction1](https://api.openfoam.com/2606/Foam_PatchFunction1.html)

## Further information

Tutorial:

* [damBreakPermeable](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/damBreakPermeable)

Source code:

* [prghPermeableAlphaTotalPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/prghPermeableAlphaTotalPressure)

API:

* [Foam::prghPermeableAlphaTotalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_prghPermeableAlphaTotalPressureFvPatchScalarField.html)

**History:** Introduced in version [v2106](https://www.openfoam.com/news/main-news/openfoam-v2106)
