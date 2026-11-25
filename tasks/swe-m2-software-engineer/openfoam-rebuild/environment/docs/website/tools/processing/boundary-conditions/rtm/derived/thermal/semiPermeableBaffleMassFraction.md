<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/semiPermeableBaffleMassFraction -->

# semiPermeableBaffleMassFraction

## Description

The `semiPermeableBaffleMassFraction` is a boundary condition that provides
a mass\-fraction boundary condition for a semi\-permeable baffle.

This condition models a baffle which is permeable to a some species and
impermeable to others. It must be used in conjunction with the
corresponding velocity condition,
`semiPermeableBaffleVelocity`.

The mass flux of a species is calculated as a coefficient multiplied by the
difference in mass fraction across the baffle.

ϕYi\=cA(Yi−Yi,n) \\phi\_{Yi} \= c A (Y\_i \- Y\_{i,n})ϕYi​\=cA(Yi​−Yi,n​)
where:

| Property | Description |
| --- | --- |
| ϕYi\\phi\_{Yi}ϕYi​ | Flux of the permeable species \[kg/s] |
| ccc | Transfer coefficient \[kg/m^2/s] |
| AAA | Patch face area \[m^2] |
| YiY\_iYi​ | Mass fraction on the patch \[\-] |
| Yi,nY\_{i,n}Yi,n​ | Mass fraction on the neighbour patch \[\-] |

A species that the baffle is permeable to will, therefore, have a
coefficient greater than zero, whilst a species that does not transfer will
have a coefficient equal to zero.

This condition calculates the species flux. The fluxes are summed up by the
velocity condition to generate the net mass transfer across the baffle.
This mass\-fraction condition then generates a corrective diffusive flux to
ensure that the correct amounts of the permeable species are transferred.

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
    type            semiPermeableBaffleMassFraction;

    // Optional entries
    c               <scalar>;
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `semiPermeableBaffleMassFraction` | word | yes | \- |
| `c` | Transfer coefficient | scalar | no | 0 |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* mappedPatchBase.H
* mixedFvPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [semiPermeableBaffleMassFraction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/semiPermeableBaffle/semiPermeableBaffleMassFraction)

API:

* [Foam::semiPermeableBaffleMassFractionFvPatchScalarField](https://api.openfoam.com/2606/Foam_semiPermeableBaffleMassFractionFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
