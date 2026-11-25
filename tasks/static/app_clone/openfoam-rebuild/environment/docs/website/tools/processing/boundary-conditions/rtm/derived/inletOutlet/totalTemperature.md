<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/totalTemperature -->

# totalTemperature

## Description

The `totalTemperature` is a fixed\-value boundary condition that sets
the static temperature from a definition of the total temperature.

The condition sets the temperature at the patch TpT\_pTp​ based on a
specification of the total temperature, T0T\_0T0​:

Tp\=T01\+γ−12γψ∣u∣2 T\_p \= \\frac{T\_0}{1 \+ \\frac{\\gamma \- 1}{2 \\gamma} \\psi \\mag{\\u}^2}Tp​\=1\+2γγ−1​ψ∣u∣2T0​​
where:

| Property | Description |
| --- | --- |
| TpT\_pTp​ | Temperature at the patch |
| T0T\_0T0​ | Total temperature |
| γ\\gammaγ | Heat capacity ratio |
| ψ\\psiψ | Compressibility |
| u\\uu | Velocity |

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
    type            totalTemperature;
    gamma           <scalar>;
    T0              <scalarField>;

    // Optional entries
    U               <word>;
    phi             <word>;
    psi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `totalTemperature` | word | yes | \- |
| `gamma` | Heat capacity ratio | scalar | yes | \- |
| `T0` | Total temperature field | scalarField | yes | \- |
| `U` | Name of velocity field | word | no | U |
| `phi` | Name of flux field | word | no | phi |
| `psi` | Name of compressibility field | word | no | none |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [totalTemperature](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/totalTemperature)

API:

* [Foam::totalTemperatureFvPatchScalarField](https://api.openfoam.com/2606/Foam_totalTemperatureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
