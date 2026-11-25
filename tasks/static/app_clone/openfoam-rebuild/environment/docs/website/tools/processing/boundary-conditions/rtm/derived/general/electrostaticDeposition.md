<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/electrostaticDeposition -->

# electrostaticDeposition

## Description

The `electrostaticDeposition` is a boundary condition to
calculate electric potential (`V`) on a given boundary
based on film thickness (`h`) and film resistance (`R`) fields
which are updated based on a given patch\-normal current density
field (`jn`), Coulombic efficiency and film resistivity.

The governing equations are as follows:

jn\=−σ∇p⊥V\=−σ(n⋅(∇V)p) j\_n \= \- \\sigma \\nabla^\\perp\_p V \= \- \\sigma (\\vec{n}\\cdot(\\nabla V)\_p)jn​\=−σ∇p⊥​V\=−σ(n⋅(∇V)p​)
dhdt\=Ceff(jn−jmin) \\frac{dh}{dt} \= C\_{eff} (j\_n \- j\_{min})dtdh​\=Ceff​(jn​−jmin​)
dRdt\=ρdhdt\=ρCeff(jn−jmin) \\frac{dR}{dt} \= \\rho \\frac{dh}{dt} \= \\rho C\_{eff} (j\_n \- j\_{min})dtdR​\=ρdtdh​\=ρCeff​(jn​−jmin​)
Vfilmn\=Vfilmo\+jnRΔ V\_{film}^n \= V\_{film}^o \+ j\_n R\_\\DeltaVfilmn​\=Vfilmo​\+jn​RΔ​
Vbody\=jnRbody V\_{body} \= j\_n R\_{body}Vbody​\=jn​Rbody​
Vpn\=Vi\+Vbody\+Vfilmn V\_p^n \= V\_i \+ V\_{body} \+ V\_{film}^nVpn​\=Vi​\+Vbody​\+Vfilmn​
where:

| Property | Description |
| --- | --- |
| jnj\_njn​ | Patch\-normal current density \[A/m^2] |
| VpnV\_p^nVpn​ | Electric potential on film\-fluid interface \[volt \= kg m^2/(A s^3\)] |
| VpoV\_p^oVpo​ | Previous time\-step electric potential on the interface \[volt] |
| VfilmV\_{film}Vfilm​ | Electric potential due to film resistance \[volt] |
| VbodyV\_{body}Vbody​ | Electric potential due to body resistance \[volt] |
| ViV\_iVi​ | Initial electric potential \[volt] |
| RΔR\_\\DeltaRΔ​ | Film resistance (finite increment) \[ohm m^2 \= kg m^4/(A^2 s^3\)] |
| RbodyR\_{body}Rbody​ | Body resistance \[ohm m^2 \= kg m^4/(A^2 s^3\)] |
| ρ\\rhoρ | Isotropic film resistivity \[ohm m \= kg m^3/(A^2 s^3\)] |
| hhh | Film thickness \[m] |
| CeffC\_{eff}Ceff​ | Volumetric Coulombic efficiency \[m^3/(A s)] |
| jminj\_{min}jmin​ | Minimum current density for deposition onset \[A/m^2] |
| σ\\sigmaσ | Isotropic conductivity of mixture \[S/m \= A^2 s^3/(kg m^3\)] |
| n\\vec{n}n | Patch\-normal unit vector \[\-] |

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
    type                    electrostaticDeposition;
    h                       <scalarField>;
    CoulombicEfficiency     <PatchFunction1>;
    resistivity             <PatchFunction1>;

    // Conditional mandatory entries

        // Option-1: single-phase
        sigma       <scalar>;

        // Option-2: multiphase
        phases
        {
            alpha.air
            {
                sigma       <scalar>;
            }
            alpha.water
            {
                sigma       <scalar>;
            }
            alpha.mercury
            {
                sigma       <scalar>;
            }
            ...
        }

    // Optional entries
    jMin                    <scalar>;
    qMin                    <scalar>;
    Rbody                   <scalar>;
    Vi                      <scalar>;
    Vanode                  <scalar>;
    qCumulative             <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `electrostaticDeposition` | word | yes | \- |
| `h` | Film thickness | scalarField | yes | \- |
| `CoulombicEfficiency` | Coulombic efficiency | PatchFunction1\<scalar\> | yes | \- |
| `resistivity` | Isotropic film resistivity | PatchFunction1\<scalar\> | yes | \- |
| `sigma` | Isotropic electrical conductivity of phase | scalar | yes | \- |
| `jMin` | Minimum current density for deposition onset | scalar | no | 0 |
| `qMin` | Minimum accumulative specific charge for deposition onset | scalar | no | 0 |
| `Rbody` | Resistance due to main body and/or pretreatment layers | scalar | no | 0 |
| `Vi` | Initial electric potential | scalar | no | 0 |
| `Vanode` | Anode electric potential | scalar | no | GREAT |
| `qCumulative` | Accumulative specific charge \[A s/m^2] | scalarField | no | 0 |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::PatchFunction1](https://api.openfoam.com/2606/Foam_PatchFunction1.html)

* Depletion or abrasion of material due to negative current is not allowed.
* When accumulative specific charge (`qCumulative`) is less than minimum
accumulative specific charge (`qMin`), no deposition occurs.
* Boundary\-condition updates are not allowed during outer corrections
to prevent spurious accumulation of film thickness.
* `resistivity`, `jMin`, `qMin` and `Rbody` are always non\-negative.

## Further information

Tutorial:

* [electrostaticDeposition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/electrostaticDeposition)

Source code:

* [electrostaticDeposition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/electrostaticDeposition)

API:

* [Foam::electrostaticDepositionFvPatchScalarField](https://api.openfoam.com/2606/Foam_electrostaticDepositionFvPatchScalarField.html)

**History:** Introduced in version [v2112](https://www.openfoam.com/news/main-news/openfoam-v2112)
