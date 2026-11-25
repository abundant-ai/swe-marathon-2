<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/icoTabulated -->

# Incompressible tabulated

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=f(p,T)\\rho \= f(p, T)ρ\=f(p,T)
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=0\\psi \= 0ψ\=0
## Usage

The `icoTabulated` equation of state is specified as:

```
equationOfState
{
    rho
    (
        (<T1> <rho1>)
        (<T2> <rho2>)
        (<T3> <rho3>)
        ...
        (<Tn> <rhon>)
    );
}

```

Where

* `rho` : List of tuples of (temperature density) describing the table

## Further information

Source code

* [icoTabulated](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/icoTabulated)
