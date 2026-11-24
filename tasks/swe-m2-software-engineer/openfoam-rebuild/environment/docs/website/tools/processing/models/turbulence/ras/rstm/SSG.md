<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/rstm/SSG -->

# Speziale, Sarkar and Gatski (SSG)

## Properties

* Reynolds stress model

## Model equations

DDt(ρϵ)\=∇ ∙ (Dϵ∇ϵ)\+Cϵ1ρGϵk−Cϵ2ρϵ2k\+Sϵ \\Ddt{\\rho \\epsilon}
 \=
 \\div \\left( D\_\\epsilon \\grad \\epsilon \\right)
 \+ C\_{\\epsilon 1} \\rho G \\frac{\\epsilon}{k}
 \- C\_{\\epsilon 2} \\rho \\frac{\\epsilon^2}{k}
 \+ S\_\\epsilonDtD​(ρϵ)\=∇∙(Dϵ​∇ϵ)\+Cϵ1​ρGkϵ​−Cϵ2​ρkϵ2​\+Sϵ​
DDt(ρR)\=∇ ∙ (ρDR∇R)−(C12ϵ\+C1∗2G)ρρkR\+ρP−13I((2−C1)ϵ−C1∗G)ρ\+C2ρϵdev(innerSqr(b))\+ρk((C3−C3∗∣b∣)dev(S)\+C4dev(twoSymm(b ∙ S))\+C5twoSymm(b ∙ Ω)) \\Ddt{\\rho \\tensor{R}}
 \=
 \\div \\left( \\rho D\_{\\tensor{R}} \\grad \\tensor{R} \\right)
 \- \\left( \\frac{C\_1}{2}\\epsilon \+ \\frac{C\_{1}^{\*}}{2}G \\right) \\rho \\frac{\\rho}{k}\\tensor{R}
 \+ \\rho P
 \- \\frac{1}{3}\\tensor{I} ((2 \- C\_1\)\\epsilon \- C\_{1}^{\*} G) \\rho
 \+ C\_2 \\rho \\epsilon \\mathrm{dev}(innerSqr(\\tensor{b}))
 \+ \\rho k
 \\left(
 (C\_3 \- C\_{3}^{\*} \\mag{\\tensor{b}}) \\mathrm{dev}(\\tensor{S})
 \+ C\_4 \\mathrm{dev}(twoSymm(\\tensor{b} \\dprod \\tensor{S}))
 \+ C\_5 twoSymm(\\tensor{b} \\dprod \\tensor{\\Omega})
 \\right)DtD​(ρR)\=∇∙(ρDR​∇R)−(2C1​​ϵ\+2C1∗​​G)ρkρ​R\+ρP−31​I((2−C1​)ϵ−C1∗​G)ρ\+C2​ρϵdev(innerSqr(b))\+ρk((C3​−C3∗​∣b∣)dev(S)\+C4​dev(twoSymm(b∙S))\+C5​twoSymm(b∙Ω))
## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        SSG;
}

```

## Further information

Source code:

* [Foam::RASModels::SSG](https://api.openfoam.com/2606/Foam_RASModels_SSG.html)

References:

* Base model: *Speziale et al.* [73](../../../../../../references.md#speziale_modelling_1991)
* Generalized gradient diffusion model of *Daly and Harlow* [13](../../../../../../references.md#daly_transport_1970)
