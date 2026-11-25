<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/nonlinear-evm/rtm/LienCubicKE -->

# Lien cubic k\-ε

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

DDt(ϵ)\=∇ ∙ (Dϵ∇ϵ)\+Cϵ1Gϵk−Cϵ2f2ϵ2k\+E \\Ddt{\\epsilon}
 \=
 \\div \\left( D\_\\epsilon \\grad \\epsilon \\right)
 \+ C\_{\\epsilon 1} G \\frac{\\epsilon}{k}
 \- C\_{\\epsilon 2} f\_2 {\\epsilon^2}{k}
 \+ EDtD​(ϵ)\=∇∙(Dϵ​∇ϵ)\+Cϵ1​Gkϵ​−Cϵ2​f2​ϵ2k\+E
## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        LienCubicKE;
}

```

## Further information

Source code:

* [Foam::incompressible::RASModels::LienCubicKE](https://api.openfoam.com/2606/Foam_incompressible_RASModels_LienCubicKE.html)

References:

* *Lien et al.* [42](../../../../../../../references.md#lien_low-reynolds-number_1996)
