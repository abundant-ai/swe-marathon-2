<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/rPolynomial -->

# Reciprocal polynomial

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=1c0\+c1T\+c2T2\+c3p\+c4pT\\rho \= \\frac{1}{c\_0 \+ c\_1 T \+ c\_2 T^2 \+ c\_3 p \+ c\_4 p T}ρ\=c0​\+c1​T\+c2​T2\+c3​p\+c4​pT1​
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=(ρ(c3\+c4T))2\\psi \= \\left( \\rho (c\_3 \+ c\_4 T) \\right)^2ψ\=(ρ(c3​\+c4​T))2
## Usage

The `rPolynomial` equation of state is specified as:

```
equationOfState
{
    C       (<c0> <c1> <c2> <c3> <c4>)
}

```

Where

* `C` : Polynomial coefficients (x5\)

## Further information

Source code

* [rPolynomial](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/rPolynomial)
