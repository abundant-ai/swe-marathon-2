<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/Boussinesq -->

# Boussinesq

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=ρ0(1−β(T−T0))\\rho \= \\rho\_0 \\left( 1 \- \\beta (T \- T\_0\) \\right)ρ\=ρ0​(1−β(T−T0​))
Entropy, SSS \[J/kg/K ]

S\=0S \= 0S\=0
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=0\\psi \= 0ψ\=0
## Usage

The `Boussinesq` equation of state is specified as:

```
equationOfState
{
    rho0        <scalar>;
    T0          <scalar>;
    beta        <scalar>;
}

```

Where

* `rho0` : Reference density \[kg/m3^33]
* `T0` : Reference temperature \[K]
* `beta` : Thermal expansion coefficient \[1/K]

## Further information

Source code

* [Boussinesq](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/Boussinesq)
