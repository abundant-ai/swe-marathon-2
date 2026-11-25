<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/perfectFluid -->

# Perfect fluid

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=ρ0\+pRT\\rho \= \\rho\_0 \+ \\frac{p}{R T}ρ\=ρ0​\+RTp​
Entropy, SSS \[J/kg/K ]

S\=−Rln⁡(ppstd)S \= \-R \\ln \\left( \\frac{p}{p\_{\\std}} \\right)S\=−Rln(pstd​p​)
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=1RT\\psi \= \\frac{1}{R T}ψ\=RT1​
## Usage

The `perfectFluid` equation of state is specified as:

```
equationOfState
{
    R           <scalar>;
    rho0        <scalar>;
}

```

Where

* `R` : Fluid constant \[J/kg/K]
* `rho0` : Reference density \[kg/m3^33]

## Further information

Source code

* [perfectFluid](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/perfectFluid)
