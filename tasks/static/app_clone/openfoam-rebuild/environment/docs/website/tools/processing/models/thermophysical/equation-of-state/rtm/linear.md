<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/linear -->

# Linear

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=ρ0\+ψp\\rho \= \\rho\_0 \+ \\psi pρ\=ρ0​\+ψp
Entropy, SSS \[J/kg/K ]

S\=−1Tψln⁡(ρ0\+ψpρ0\+ψpstd)S \= \-\\frac{1}{T \\psi}\\ln\\left(\\frac{\\rho\_0 \+ \\psi p}{\\rho\_0 \+ \\psi p\_{\\std}}\\right)S\=−Tψ1​ln(ρ0​\+ψpstd​ρ0​\+ψp​)
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=constant\\psi \= constantψ\=constant
## Usage

The `linear` equation of state is specified as:

```
equationOfState
{
    psi         <scalar>;
    rho0        <scalar>;
}

```

Where

* `psi` : Compressibility \[s2^22/m2^22]
* `rho0` : Reference density \[kg/m3^33]

## Further information

Source code

* [linear](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/linear)
