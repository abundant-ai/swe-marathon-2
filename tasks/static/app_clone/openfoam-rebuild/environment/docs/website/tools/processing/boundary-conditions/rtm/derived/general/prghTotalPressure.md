<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/prghTotalPressure -->

# prghTotalPressure

## Description

The `prghTotalPressure` is a boundary condition that provides
static pressure condition for `p_rgh`, calculated as:

prgh\=p−ρg(h−href) p\_{rgh} \= p \- \\rho g (h \- h\_{ref})prgh​\=p−ρg(h−href​)
p\=p0−0\.5ρ∣u∣2 p \= p\_0 \- 0\.5 \\rho \|\\vec{u}\|^2p\=p0​−0\.5ρ∣u∣2
where:

| Property | Description |
| --- | --- |
| prghp\_{rgh}prgh​ | Pseudo hydrostatic pressure \[Pa] |
| ppp | Static pressure \[Pa] |
| p0p\_0p0​ | Total pressure \[Pa] |
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
    type            prghTotalPressure;
    p0              <scalarField>;

    // Optional entries
    rho             <word>;
    phi             <word>;
    U               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `prghTotalPressure` | word | yes | \- |
| `p0` | Total pressure field | word | yes | \- |
| `rho` | Name of density field | word | no | rho |
| `phi` | Name of flux field | word | no | phi |
| `U` | Name of velocity field | word | no | U |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [simpleCarSolarPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/simpleCarSolarPanel)

Source code:

* [prghTotalPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/prghTotalPressure)

API:

* [Foam::prghTotalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_prghTotalPressureFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
