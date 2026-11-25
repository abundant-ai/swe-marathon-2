<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/nonlinear-evm/rtm/ShihQuadraticKE -->

# Shih quadratic k\-ε

## Properties

* Incompressible only

## Model equations

The turbulence kinetic energy equation is given by:

DDt(k)\=∇ ∙ (Dk∇k)\+G−ϵ \\Ddt{k}
 \=
 \\div \\left(D\_k \\grad k \\right)
 \+ G
 \- \\epsilonDtD​(k)\=∇∙(Dk​∇k)\+G−ϵ
and the dissipation rate by:

DDt(ϵ)\=∇ ∙ (Dϵ∇ϵ)\+C1Gϵk−C2ϵ2k \\Ddt{\\epsilon}
 \=
 \\div \\left( D\_{\\epsilon} \\grad \\epsilon \\right)
 \+ C\_1 G \\frac{\\epsilon}{k}
 \- C\_2 \\frac{\\epsilon^2}{k}DtD​(ϵ)\=∇∙(Dϵ​∇ϵ)\+C1​Gkϵ​−C2​kϵ2​
The turbulence generation, GGG is given by:

G\=\[νt(∇u\+(∇u)T)−τnl] ⁣:∇u G \= \\left\[\\nu\_t \\left( \\grad \\u \+ \\left(\\grad \\u\\right)^T \\right) \- \\tensor{\\tau}\_{nl}\\right] \\colon \\grad \\uG\=\[νt​(∇u\+(∇u)T)−τnl​]:∇u
where τnl\\tensor{\\tau}\_{nl}τnl​ is the non\-linear stress.

## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        ShihQuadraticKE;
}

```

## Further information

Source code:

* [Foam::incompressible::RASModels::ShihQuadraticKE](https://api.openfoam.com/2606/Foam_incompressible_RASModels_ShihQuadraticKE.html)

Reference:

* *Shih et al.* [63](../../../../../../../references.md#shih_realizable_1993)
