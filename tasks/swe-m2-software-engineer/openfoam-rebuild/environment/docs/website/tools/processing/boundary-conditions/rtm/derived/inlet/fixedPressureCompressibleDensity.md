<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/fixedPressureCompressibleDensity -->

# fixedPressureCompressibleDensity

## Description

The `fixedPressureCompressibleDensity` is a pressure boundary condition that
calculates a (liquid) compressible density as a function of pressure and
fluid properties.

The governing equations are as follows:

ρ\=ρl,sat\+ψl∗(p−psat) \\rho \= \\rho\_{l,sat} \+ \\psi\_l\*(p \- p\_{sat})ρ\=ρl,sat​\+ψl​∗(p−psat​)
where:

| Property | Description |
| --- | --- |
| ρ\\rhoρ | Density \[kg/m^3] |
| ρl,sat\\rho\_{l,sat}ρl,sat​ | Saturation liquid density \[kg/m^3] |
| ψl\\psi\_lψl​ | Liquid compressibility \[\-] |
| ppp | Pressure \[Pa] |
| psatp\_{sat}psat​ | Saturation pressure \[Pa] |

The variables ρl,sat,psat\\rho\_{l,sat}, p\_{sat}ρl,sat​,psat​ and ψl\\psi\_lψl​ are retrieved from the
`thermodynamicProperties` dictionary.

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
    type            fixedPressureCompressibleDensity;

    // Optional entries
    p               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedPressureCompressibleDensity` | word | yes | \- |
| `p` | Name of pressure field | word | no | p |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [fixedPressureCompressibleDensity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedPressureCompressibleDensity)

API:

* [Foam::fixedPressureCompressibleDensityFvPatchScalarField](https://api.openfoam.com/2606/Foam_fixedPressureCompressibleDensityFvPatchScalarField.html)

**History:** Introduced in version [1\.6](https://www.openfoam.com/news/main-news/openfoam-1.6)
