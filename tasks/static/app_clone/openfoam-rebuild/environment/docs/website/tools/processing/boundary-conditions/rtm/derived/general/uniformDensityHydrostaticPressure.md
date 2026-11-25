<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/uniformDensityHydrostaticPressure -->

# uniformDensityHydrostaticPressure

## Description

The `uniformDensityHydrostaticPressure` is a boundary condition that
provides a hydrostatic pressure condition, calculated as:

phyd\=pref\+ρg(x−xref) p\_{hyd} \= p\_{ref} \+ \\rho g (x \- x\_{ref})phyd​\=pref​\+ρg(x−xref​)
where:

| Property | Description |
| --- | --- |
| phydp\_{hyd}phyd​ | Hydrostatic pressure \[Pa] |
| prefp\_{ref}pref​ | Reference pressure \[Pa] |
| xrefx\_{ref}xref​ | Reference point in Cartesian coordinates |
| ρ\\rhoρ | Density (assumed uniform) |
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
    type            uniformDensityHydrostaticPressure;
    rho             <scalar>;
    pRefValue       <scalar>;
    pRefPoint       <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `uniformDensityHydrostaticPressure` | word | yes | \- |
| `rho` | Value of density | scalar | yes | \- |
| `pRefValue` | Reference pressure \[Pa] | scalar | yes | \- |
| `pRefPoint` | Reference pressure location | vector | yes | \- |

The inherited entries are elaborated in:

* [fixedValueFvPatchField.H](fixedValue.md)

## Further information

Tutorial:

* N/A

Source code:

* [uniformDensityHydrostaticPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/uniformDensityHydrostaticPressure)

API:

* [Foam::uniformDensityHydrostaticPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_uniformDensityHydrostaticPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
