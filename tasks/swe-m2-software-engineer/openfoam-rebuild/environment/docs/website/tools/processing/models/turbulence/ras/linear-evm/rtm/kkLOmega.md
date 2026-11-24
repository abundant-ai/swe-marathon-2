<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/kkLOmega -->

# k\-kl\-ω

## Properties

* incompressible only
* three\-equation model
* low Reynolds number
* transition modelling

## Model equations

Specific dissipation rate equation:

DDt(ω)\=∇ ∙ (Dω∇ω)\+Cw1Pktωkt−(1\.0−CwRfw)kl(Rbp\+Rnat)ωkt−Cw2fw2ω2\+Cw3fωαtfw2kt0\.5y3 \\Ddt{\\omega}
 \=
 \\div \\left(D\_\\omega \\grad \\omega\\right)
 \+ C\_{w1} P\_{kt} \\frac{\\omega}{k\_t}
 \- \\left(1\.0 \- \\frac{C\_{wR}}{f\_w} \\right) k\_l \\left(R\_{bp} \+ R\_{nat}\\right) \\frac{\\omega}{k\_t}
 \- C\_{w2} f\_w^2 \\omega^2
 \+ C\_{w3} f\_\\omega \\alpha\_t f\_w^2 \\frac{k\_t^{0\.5}}{y^3}DtD​(ω)\=∇∙(Dω​∇ω)\+Cw1​Pkt​kt​ω​−(1\.0−fw​CwR​​)kl​(Rbp​\+Rnat​)kt​ω​−Cw2​fw2​ω2\+Cw3​fω​αt​fw2​y3kt0\.5​​
Laminar kinetic energy equation:

DDt(kl)\=∇ ∙ (ν∇kl)\+Pkl−Rbp\+Rnat\+Dl \\Ddt{k\_l}
 \=
 \\div \\left( \\nu \\grad k\_l \\right)
 \+ P\_{kl}
 \- R\_{bp} \+ R\_{nat} \+ D\_lDtD​(kl​)\=∇∙(ν∇kl​)\+Pkl​−Rbp​\+Rnat​\+Dl​
Turbulent kinetic energy equation:

DDt(kt)\=∇ ∙ (Dk∇kt)\+Pkt\+(Rbp\+Rnat)kl−ω\+Dt \\Ddt{k\_t}
 \=
 \\div \\left(D\_k \\grad k\_t\\right)
 \+ P\_{kt}
 \+ \\left(R\_{bp} \+ R\_{nat}\\right) k\_l
 \- \\omega \+ D\_tDtD​(kt​)\=∇∙(Dk​∇kt​)\+Pkt​\+(Rbp​\+Rnat​)kl​−ω\+Dt​
## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        kkLOmega;
}

```

## Further information

Source code:

* [Foam::incompressible::RASModels::kkLOmega](https://api.openfoam.com/2606/Foam_incompressible_RASModels_kkLOmega.html)

References:

* Standard model: *Walters and Cokljat* [85](../../../../../../../references.md#walters_three-equation_2008)
* Corrections to the standard model: *Furst* [18](../../../../../../../references.md#furst_numerical_2013)
