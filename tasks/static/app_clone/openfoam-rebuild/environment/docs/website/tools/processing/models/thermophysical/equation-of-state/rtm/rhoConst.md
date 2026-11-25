<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/rhoConst -->

# Constant density

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=ρ0\\rho \= \\rho\_0ρ\=ρ0​
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=0\\psi \= 0ψ\=0
## Usage

The `rhoConst` equation of state is specified as:

```
equationOfState
{
    rho         <scalar>;
}

```

Where

* `rho` : Constant density \[kg/m3^33]

## Further information

Source code

* [rhoConst](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/rhoConst)
