<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/enthalpySorption -->

# enthalpySorption

## Description

The `enthalpySorption` is a boundary condition that provides
a temperature boundary condition which works in conjunction with the
`speciesSorption` condition for species.

This boundary condition substracts or adds enthalpy associated with the
adsorption provided by the `speciesSorption` condition.

It can handle two enthalpy models:

* estimate
* calculated

On top of this, the enthalpy associated with the sensible enthalpy
corresponding with the species transport can be added using `includeHs`.

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
    type                enthalpySorption;
    enthalpyModel       <word>;
    species             <word>;

    // Conditional mandatory entries

    // when enthalpyModel == calculated
    enthalpyTable       <Function1<scalar>>

        // enthalpyTable
        // {
        //     type            table;
        //     values          ((0 0)(1 50));
        // }

    // Optional entries
    includeHs           <bool>;
    C                   <scalar>;
    Hvap                <scalar>;
    dhdt                <scalarField>;
    p                   <word>;
    T                   <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `enthalpySorption` | word | yes | \- |
| `enthalpyModel` | Adsorption enthalpy model | word | yes | \- |
| `species` | Name of associated species | word | yes | \- |
| `enthalpyTable` | Calculated enthalpy model table | Function1\<scalar\> | no | \- |
| `includeHs` | Include sensible enthalpy | bool | no | true |
| `C` | Estimate enthalpy model constant | scalar | no | 0 |
| `Hvap` | Evaporation heat for species | scalar | no | 0 |
| `p` | Name of operand pressure field | word | no | p |
| `T` | Name of operand temperature field | word | no | T |
| `dhdt` | Enthalpy change on cells next to patch \[J/kg] | scalarField | no | Zero |

The inherited entries are elaborated in:

* zeroGradientFvPatchFields.H
* Function1\.H
* boundarySourcePatch.H

Options for the `enthalpyModel` entry:

| Property | Description |
| --- | --- |
| `estimated` | Enthalpy is estimated |
| `calculated` | Enthalpy is calculated based on enthalpyTable |

## Further information

Tutorial:

* [groundAbsorption](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/rhoReactingFoam/groundAbsorption)

Source code:

* [enthalpySorption](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/derivedFvPatchFields/enthalpySorption)

API:

* [Foam::enthalpySorptionFvPatchScalarField](https://api.openfoam.com/2606/Foam_enthalpySorptionFvPatchScalarField.html)

**History:** Introduced in version [2206](https://www.openfoam.com/news/main-news/openfoam-2206)
