<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/icoPolynomial -->

# Incompressible polynomial

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=∑i\=1NciTi−1\\rho \= \\sum\_{i\=1}^N c\_i T^{i\-1}ρ\=i\=1∑N​ci​Ti−1
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=0\\psi \= 0ψ\=0
## Usage

The `icoPolynomial` equation of state is specified as:

```
equationOfState
{
    rhoCoeffs<8>        (<c1> <c2> <c3> <c4> <c5> <c6> <c7> <c8>);
}

```

Where

* `rhoCoeffs<8>` : Polynomial coefficients (x8\)

## Further information

Source code

* [icoPolynomial](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/icoPolynomial)
