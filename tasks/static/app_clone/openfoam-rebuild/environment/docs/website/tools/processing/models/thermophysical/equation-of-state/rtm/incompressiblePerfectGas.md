<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/incompressiblePerfectGas -->

# Incompressible perfect gas

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=prefRT\\rho \= \\frac{p\_{\\ref}}{R T}ρ\=RTpref​​
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=0\\psi \= 0ψ\=0
## Usage

The `incompressiblePerfectGas` equation of state is specified as:

```
equationOfState
{
    pRef        <scalar>;
}

```

Where

* `pRef` : Reference pressure \[Pa]

## Further information

Source code

* [incompressiblePerfectGas](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/incompressiblePerfectGas)
