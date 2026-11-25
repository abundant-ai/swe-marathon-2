<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/rtm/PengRobinsonGas -->

# Peng\-Robinson gas

The Peng\-Robinson [57](../../../../../../references.md#peng_new_1976) equation of state for gases.

Density, ρ\\rhoρ \[kg/m3^33]

ρ\=pZRT\\rho \= \\frac{p}{Z R T}ρ\=ZRTp​
Here, ZZZ is computed from the cubic equation:

Z3−(1−B)Z2\+(A−2B−3B2)Z−(AB−B2−B3)\=0Z^3 \- (1 \- B)Z^2 \+ (A \- 2B \- 3B^2\)Z \- (AB \- B^2 \- B^3\) \= 0Z3−(1−B)Z2\+(A−2B−3B2)Z−(AB−B2−B3)\=0
Where:

A\=αapR2T2;B\=bpRT.A \= \\frac{\\alpha a p}{R^2 T^2}; B \= \\frac{bp}{RT}.A\=R2T2αap​;B\=RTbp​.
with:

* a\=0\.45724R2Tc2pca \= 0\.45724 \\frac{R^2 T\_c^2}{p\_c}a\=0\.45724pc​R2Tc2​​
* b\=0\.07780RTcpcb \= 0\.07780 \\frac{R T\_c}{p\_c}b\=0\.07780pc​RTc​​
* α\=(1\+κ(1−Tr0\.5))2\\alpha \= \\left(1 \+ \\kappa (1 \- T\_r^{0\.5}) \\right)^2α\=(1\+κ(1−Tr0\.5​))2
* κ\=0\.37464\+1\.564226ω−0\.26992ω2\\kappa \= 0\.37464 \+ 1\.564226 \\omega \- 0\.26992 \\omega^2κ\=0\.37464\+1\.564226ω−0\.26992ω2
* Tr\=TTcT\_r \= \\frac{T}{T\_c}Tr​\=Tc​T​

Entropy, SSS \[J/kg/K ]

S\=...S \= ...S\=...
Compressibility, ψ\\psiψ \[s2^22/m2^22]

ψ\=1ZRT\\psi \= \\frac{1}{Z R T}ψ\=ZRT1​
## Usage

The `PengRobinsonGas` equation of state is specified as:

```
equationOfState
{
    Tc          <scalar>;
    Vc          <scalar>;
    Pc          <scalar>;
    omega       <scalar>;
}

```

Where

* `Tc` : Critical temperature \[K]
* `Vc` : Critical volume \[m3^33/kmol]
* `Pc` : Critical pressure \[Pa]
* `omega` : Accentric factor \[\-]

## Further information

Source code

* [PengRobinsonGas](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/equationOfState/PengRobinsonGas)
