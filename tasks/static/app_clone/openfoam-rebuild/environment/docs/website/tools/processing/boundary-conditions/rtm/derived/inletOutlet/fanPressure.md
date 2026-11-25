<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/fanPressure -->

# fanPressure

## Description

The `fanPressure` is a pressure boundary condition to assign either a pressure
inlet or outlet total pressure condition for a fan. The condition sets the
static pressure from a definition of the total pressure and pressure drop as a
function of volumetric flow rate across the patch.

The non\-dimensional flux is calculated as follows:

phi\=4m˙ρπ2dm3ω phi \= \\frac{4 \\dot{m}}{\\rho \\pi^2 d\_m^3 \\omega}phi\=ρπ2dm3​ω4m˙​
The non\-dimensional flux is calculated as follows:

Ψ\=2ΔPρ(πωdm) \\Psi \= \\frac{2 \\Delta P}{\\rho (\\pi \\omega d\_m)}Ψ\=ρ(πωdm​)2ΔP​

| Property | Description |
| --- | --- |
| dmd\_mdm​ | Fan mean diameter \[m] |
| ΔP\\Delta PΔP | Pressure drop |
| ω\\omegaω | Rotational speed \[rad/s] |
| m˙\\dot{m}m˙ | Mass flow rate |

The non\-dimensional table should be given as Ψ\=F(ϕ)\\Psi \= F(\\phi)Ψ\=F(ϕ).

The condition sets the static pressure at the patch ppp\_ppp​ based on a
specification of the total pressure, p0p\_0p0​, and pressure drop,
pdp\_dpd​, specified as a function of the volumetric flow rate.

pp\=p0−pd p\_p \= p\_0 \- p\_dpp​\=p0​−pd​
## Usage

The condition requires entries in both the `boundary` and field files.

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
    type            fanPressure;
    fanCurve        <Function1<scalar>>;
    direction       <word>;

    // Optional entries
    nonDimensional  <bool>;

    // Conditional entries

      // if 'nonDimensional' is true
      rpm           <Function1<scalar>>;
      dm            <Function1<scalar>>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fan` | word | yes | \- |
| `fanCurve` | Dataset of pressure vs flow rate | Function1\<scalar\> | yes | \- |
| `direction` | Direction of flow through fan | word | yes | \- |
| `nonDimensional` | Flag to use non\-dimensional curves | bool | no | false |
| `rpm` | Fan rpm (for non\-dimensional curve) | Function1\<scalar\> | conditional | \- |
| `dm` | Fan mean diameter (for non\-dimensional curve) | Function1\<scalar\> | conditional | \- |

Options for the `direction` entry:

| Property | Description |
| --- | --- |
| `in` | Into the fan |
| `out` | Out of the fan |

The inherited entries are elaborated in:

* [Foam::totalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_totalPressureFvPatchScalarField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* For compatibility with older versions (OpenFOAM\-v2006 and earlier),
a missing `fanCurve` keyword is treated as a `tableFile` and makes
the `file` keyword mandatory.

## Further information

Tutorial:

* [TJunctionFan](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunctionFan)

Source code:

* [fanPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fanPressure)

API:

* [Foam::fanPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_fanPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
