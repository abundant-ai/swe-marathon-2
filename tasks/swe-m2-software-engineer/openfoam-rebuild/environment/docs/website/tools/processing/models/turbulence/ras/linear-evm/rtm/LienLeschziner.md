<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/LienLeschziner -->

# Lien\-Leschziner

## Properties

* Incompressible only
* Two\-equation model

## Model equations

The turbulence kinetic energy equation is given by:

DDt(k)\=∇ ∙ (Dk∇k)\+G−ϵ \\Ddt{k}
 \=
 \\div \\left( D\_k \\grad k \\right)
 \+ G
 \- \\epsilonDtD​(k)\=∇∙(Dk​∇k)\+G−ϵ
and the turbulence dissipation rate equation by:

DDt(ϵ)\=∇ ∙ (Dϵ∇ϵ)\+Cϵ1Gϵ/k−Cϵ2f2ϵ2/k\+E \\Ddt{\\epsilon}
 \=
 \\div \\left( D\_\\epsilon \\grad \\epsilon \\right)
 \+ C\_{\\epsilon 1} G \\epsilon/k
 \- C\_{\\epsilon 2} f\_2 \\epsilon^2/k
 \+ EDtD​(ϵ)\=∇∙(Dϵ​∇ϵ)\+Cϵ1​Gϵ/k−Cϵ2​f2​ϵ2/k\+E
## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        LienLeschziner;
}

```

## Further information

Source code:

* [Foam::incompressible::RASModels::LienLeschziner](https://api.openfoam.com/2606/Foam_incompressible_RASModels_LienLeschziner.html)

References:

* Standard model: *Lien and Leschziner* [43](../../../../../../../references.md#lien_pressure-velocity_1993)
