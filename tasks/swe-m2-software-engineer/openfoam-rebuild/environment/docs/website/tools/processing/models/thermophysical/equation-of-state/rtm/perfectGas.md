<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/perfectGas -->

# Perfect gas

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=pRT\\rho \= \\frac{p}{R T}ρ\=RTp​
Entropy, SSS \[J/kg/K ]

S\=−Rln⁡(ppstd)S \= \-R \\ln \\left( \\frac{p}{p\_{\\std}} \\right)S\=−Rln(pstd​p​)
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=1RT\\psi \= \\frac{1}{R T}
ψ\=RT1​
## Usage

The `perfectGas` equation of state is specified as:

```
equationOfState
{
    // empty - no input needed
}

```

## Further information

Source code

* [perfectGas](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/perfectGas)
