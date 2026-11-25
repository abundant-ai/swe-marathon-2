<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/prghPressure -->

# prghPressure

## Description

The `prghPressure` is a boundary condition that provides static pressure
condition for `p_rgh`, calculated as:

prgh\=p−ρg(h−href) p\_{rgh} \= p \- \\rho g (h \- h\_{ref})prgh​\=p−ρg(h−href​)
where:

| Property | Description |
| --- | --- |
| prghp\_{rgh}prgh​ | Pseudo hydrostatic pressure \[Pa] |
| ppp | Static pressure \[Pa] |
| hhh | Height in the opposite direction to gravity |
| hrefh\_{ref}href​ | Reference height in the opposite direction to gravity |
| ρ\\rhoρ | Density |
| ggg | Acceleration due to gravity \[m/s^2] |

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
    type            prghPressure;
    p               <scalarField>;

    // Optional entries
    rho             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `prghPressure` | word | yes | \- |
| `p` | Static pressure | scalarField | yes | \- |
| `rho` | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [wallBoiling1D\_2phase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingMultiphaseEulerFoam/RAS/wallBoiling1D_2phase)

Source code:

* [prghPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/prghPressure)

API:

* [Foam::prghPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_prghPressureFvPatchScalarField.html)

**History:** Introduced in version [2\.3\.0](https://www.openfoam.com/news/main-news/openfoam-2.3.0)
