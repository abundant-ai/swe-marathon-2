<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/phaseHydrostaticPressure -->

# Untitled

\-\-
title: phaseHydrostaticPressure
copyright:

* Copyright (C) 2023 OpenCFD Ltd.
tags:
* boundary conditions
menu\_id: boundary\-conditions\-phaseHydrostaticPressure
license: CC\-BY\-NC\-ND\-4\.0
menu\_parent: boundary\-conditions\-general
group: boundary\-conditions\-general

---

## Description

The `phaseHydrostaticPressure` is a generic boundary condition that
provides a phase\-based hydrostatic pressure condition, calculated as:

phyd\=pref\+ρg(x−xref) p\_{hyd} \= p\_{ref} \+ \\rho g (x \- x\_{ref})phyd​\=pref​\+ρg(x−xref​)
where:

| Property | Type |
| --- | --- |
| phydp\_{hyd}phyd​ | Hyrostatic pressure \[Pa] |
| prefp\_{ref}pref​ | Reference pressure \[Pa] |
| xrefx\_{ref}xref​ | Reference point in Cartesian coordinates |
| ρ\\rhoρ | Density (assumed uniform) |
| ggg | Acceleration due to gravity \[m/s2] |

The values are assigned according to the phase\-fraction field:

* 1: apply phydp\_{hyd}phyd​
* 0: apply a zero\-gradient condition

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            mappedPatch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            phaseHydrostaticPressure;
    rho             <scalar>;
    pRefValue       <scalar>;
    pRefPoint       <vector>;

    // Optional entries
    phaseFraction   <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `phaseHydrostaticPressure` | word | yes | \- |
| `rho` | Constant value of density in the far field | scalar | yes | \- |
| `pRefValue` | Reference pressure \[Pa] | scalar | yes | \- |
| `pRefPoint` | Reference pressure location | vector | yes | \- |
| `phaseFraction` | Name of phase\-fraction field | word | no | alpha |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [phaseHydrostaticPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/phaseHydrostaticPressure)

API:

* [Foam::phaseHydrostaticPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_phaseHydrostaticPressureFvPatchScalarField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
