<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/totalPressure -->

# totalPressure

## Description

The `totalPressure` is a boundary condition that sets the static pressure at
the patch ppp\_ppp​ based on a specification of the total pressure, p0p\_0p0​.
The mode of operation is determined via the input entries and the dimensions
of the convective flux, phi (ϕ\\phiϕ).

Four variants are possible:

### Incompressible subsonic

Patch pressure described by subtracting the dynamic pressure from the total
pressure, where the flux has dimensions of m3/sm^3/sm3/s.

pp\=p0−12∣u∣2 p\_p \= p\_0 \- \\frac{1}{2}\\mag{\\u}^2pp​\=p0​−21​∣u∣2
where:

| Property | Description |
| --- | --- |
| ppp\_ppp​ | Incompressible pressure at patch \[m^2/s^2] |
| p0p\_0p0​ | Incompressible total pressure \[m^2/s^2] |
| u\\uu | Velocity |

### Compressible subsonic

Patch pressure described by subtracting the dynamic pressure from the total
pressure, where the flux has dimensions of kg/skg/skg/s.

pp\=p0−12ρ∣u∣2 p\_p \= p\_0 \- \\frac{1}{2}\\rho\\mag{\\u}^2pp​\=p0​−21​ρ∣u∣2
where:

| Property | Description |
| --- | --- |
| ppp\_ppp​ | Pressure at patch \[Pa] |
| p0p\_0p0​ | Total pressure \[Pa] |
| ρ\\rhoρ | Density \[kg/m^3] |
| u\\uu | Velocity |

### Compressible transonic (γ\=1\\gamma \= 1γ\=1)

Ratio of specific heats, γ\=Cp/Cv\\gamma \= C\_p/C\_vγ\=Cp​/Cv​ equal to 1\.

pp\=p01\+12ψ∣u∣2 p\_p \= \\frac{p\_0}{1 \+ \\frac{1}{2} \\psi \\mag{\\u}^2}pp​\=1\+21​ψ∣u∣2p0​​
where:

| Property | Description |
| --- | --- |
| ppp\_ppp​ | Pressure at patch \[Pa] |
| p0p\_0p0​ | Total pressure \[Pa] |
| ψ\\psiψ | Compressibility \[m^2/s^2] |
| u\\uu | Velocity |

### Compressible supersonic (γ\>1\\gamma \> 1γ\>1)

Ratio of specific heats, γ\=Cp/Cv\\gamma \= C\_p/C\_vγ\=Cp​/Cv​ greater than 1\.

pp\=p0(1\+γ−12ψ∣u∣2)γγ−1 p\_p \= \\frac{p\_0}{\\left(1 \+ \\frac{\\gamma \- 1}{2} \\psi \\mag{\\u}^2\\right)^{\\frac{\\gamma}{\\gamma \- 1}}}pp​\=(1\+2γ−1​ψ∣u∣2)γ−1γ​p0​​

| Property | Description |
| --- | --- |
| ppp\_ppp​ | Pressure at patch \[Pa] |
| p0p\_0p0​ | Total pressure \[Pa] |
| ψ\\psiψ | Compressibility \[m^2/s^2] |
| GGG | Coefficient given by γ1−γ\\frac{\\gamma}{1\-\\gamma}1−γγ​ |
| u\\uu | Velocity |

The modes of operation are set by the dimensions of the pressure field
to which this boundary condition is applied, the `psi` entry and the value
of `gamma`:

| Mode | Dimensions | psi | gamma |
| --- | --- | --- | --- |
| Incompressible subsonic | p/rho | \- | \- |
| Compressible subsonic | p | none | \- |
| Compressible transonic | p | psi | 1 |
| Compressible supersonic | p | psi | \> 1 |

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
    type            totalPressure;

    // Conditional entries

        // Incompressible subsonic
        rho             none;
        p0              uniform 0;

        // Compressible subsonic
        p0              uniform 100000;

        // Compressible transonic
        psi             psi;
        p0              uniform 100000;

        // Compressible supersonic
        psi             psi;
        gamma           1.4;
        p0              uniform 100000;

    // Optional entries
    U               <word>;
    phi             <word>;
    rho             <word>;
    psi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `totalPressure` | word | yes | \- |
| `p0` | Total pressure field | scalarField | yes | \- |
| `U` | Name of velocity field | word | no | U |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `psi` | Name of compressibility field | word | no | none |
| `gamma` | Heat capacity ratio | scalar | conditional | \- |

## Further information

Tutorial:

* [windAroundBuildings](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/windAroundBuildings)

Source code:

* [supersonicFreestream](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/supersonicFreestream)

API:

* [Foam::totalPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_totalPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
