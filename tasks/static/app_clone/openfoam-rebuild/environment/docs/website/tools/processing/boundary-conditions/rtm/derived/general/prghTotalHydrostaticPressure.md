<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/prghTotalHydrostaticPressure -->

# prghTotalHydrostaticPressure

## Description

The `prghTotalHydrostaticPressure` is a boundary condition that provides
static pressure condition for `p_rgh`, calculated as:

prgh\=phrgh−0\.5ρ∣u∣2 p\_{rgh} \= {ph}\_{rgh} \- 0\.5 \\rho \|\\vec{u}\|^2prgh​\=phrgh​−0\.5ρ∣u∣2
where:

| Property | Description |
| --- | --- |
| prghp\_{rgh}prgh​ | Pressure: ρg(h−href)\\rho g (h \- h\_{ref})ρg(h−href​) \[Pa] |
| ppp | Hydrostatic pressure: ρg(h−href)\\rho g (h \- h\_{ref})ρg(h−href​) \[Pa] |
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
    type            prghTotalHydrostaticPressure;

    // Optional entries
    rho             <word>;
    phi             <word>;
    U               <word>;
    ph_rgh          <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `prghTotalHydrostaticPressure` | word | yes | \- |
| `rho` | Name of density field | word | no | rho |
| `phi` | Name of flux field | word | no | phi |
| `U` | Name of velocity field | word | no | U |
| `ph_rgh` | Name of ph\_rgh field | word | no | ph\_rgh |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [smallPoolFire2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/smallPoolFire2D)

Source code:

* [prghTotalHydrostaticPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/prghTotalHydrostaticPressure)

API:

* [Foam::prghTotalHydrostaticPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_prghTotalHydrostaticPressureFvPatchScalarField.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
