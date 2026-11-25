<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/adiabaticPerfectFluid -->

# Adiabatic perfect fluid

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=ρ0p\+Bp0\+B1γ\\rho \= \\rho\_0 \\frac{p \+ B}{p\_0 \+ B}^{\\frac{1}{\\gamma}}ρ\=ρ0​p0​\+Bp\+B​γ1​
Entropy, SSS \[J/kg/K ]

S\=−(p0\+B)1γ(p\+B)1−1γ−(Pstd\+B)nρ0T(1−1γ)S \= \-(p\_0 \+ B)^\\frac{1}{\\gamma}
 \\frac{(p \+ B)^{1 \- \\frac{1}{\\gamma}} \- (P\_{\\std} \+ B)^n}{\\rho\_0 T (1 \- \\frac{1}{\\gamma})}S\=−(p0​\+B)γ1​ρ0​T(1−γ1​)(p\+B)1−γ1​−(Pstd​\+B)n​
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=ρ0γ(p0\+B)p\+Bp0\+B1γ−1\\psi \= \\frac{\\rho\_0}{\\gamma(p\_0 \+ B)} \\frac{p \+ B}{p\_0 \+ B}^{\\frac{1}{\\gamma} \- 1}ψ\=γ(p0​\+B)ρ0​​p0​\+Bp\+B​γ1​−1
## Usage

The `adiabaticPerfectFluid` equation of state is specified as:

```
equationOfState
{
    p0          <scalar>;
    rho0        <scalar>;
    gamma       <scalar>;
    B           <scalar>;
}

```

Where

* `p0` : Reference pressure \[Pa]
* `rho0` : Reference density \[kg/m3^33]
* `gamma` : Isentropic exponent \[\-]
* `B` : Pressure offset for a stiffened gas \[Pa]

## Further information

Source code

* [adiabaticPerfectFluid](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/adiabaticPerfectFluid)
