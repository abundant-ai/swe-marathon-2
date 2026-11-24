<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/realizableKEpsilon -->

# Realizable k\-ε

## Properties

## Model equations

The turbulence kinetic energy equation is given by:

DDt(ρk)\=∇ ∙ (ρDk∇k)\+ρG−23ρ(∇ ∙ u)k−ρϵ\+Sk \\Ddt{\\rho k}
 \=
 \\div \\left(\\rho D\_k \\grad k\\right)
 \+ \\rho G
 \- \\frac{2}{3}\\rho \\left(\\div \\u\\right) k
 \- \\rho \\epsilon
 \+ S\_kDtD​(ρk)\=∇∙(ρDk​∇k)\+ρG−32​ρ(∇∙u)k−ρϵ\+Sk​
and the dissipation rate by:

DDt(ρϵ)\=∇ ∙ (ρDϵ∇ϵ)\+C1ρ∣S∣ϵ−C2ρϵ2k\+(νϵ)0\.5\+Sϵ \\Ddt{\\rho \\epsilon}
 \=
 \\div \\left(\\rho D\_\\epsilon \\grad \\epsilon \\right)
 \+ C\_1 \\rho \\mag{\\tensor{S}} \\epsilon
 \- C\_2 \\rho \\frac{\\epsilon^2}{k \+ \\left(\\nu \\epsilon\\right)^{0\.5}}
 \+ S\_\\epsilonDtD​(ρϵ)\=∇∙(ρDϵ​∇ϵ)\+C1​ρ∣S∣ϵ−C2​ρk\+(νϵ)0\.5ϵ2​\+Sϵ​
The turbulence viscosity is calculated using:

νt\=Cμk2ϵ \\nu\_t \= C\_{\\mu} \\frac{k^2}{\\epsilon}νt​\=Cμ​ϵk2​
where the CμC\_{\\mu}Cμ​ is given by:

Cμ\=1A0\+AsU∗kϵ C\_{\\mu} \= \\frac{1}{A\_0 \+ A\_s U^{\*} \\frac{k}{\\epsilon}}Cμ​\=A0​\+As​U∗ϵk​1​
## Default model coefficients

## Initialisation

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        realizableKE;
}

```

## Boundary conditions

Walls

## Further information

Source code:

* [Foam::RASModels::realizableKE](https://api.openfoam.com/2606/Foam_RASModels_realizableKE.html)

References:

* *Shih et al.* [62](../../../../../../../references.md#shih_new_1995)
