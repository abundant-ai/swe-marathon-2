<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/rstm/ -->

# Reynolds stress transport models (RSTM)

Reynolds stress transport turbulence model selections include:

* [Launder, Reece and Rodi (LRR)](LRR.md)
* [Speziale, Sarkar and Gatski (SSG)](SSG.md)

## Background

The Reynolds stress transport equation reads:

DDt(R)\=P⏟production\+Π⏟pressure−strain−ϵ⏟dissipation\+D⏟diffusion\+Ω⏟rotation \\Ddt{\\tensor{R}}
 \=
 \\underbrace{\\tensor{P}}\_{production}
 \+ \\underbrace{\\tensor{\\Pi}}\_{pressure\-strain}
 \- \\underbrace{\\tensor{\\epsilon}}\_{dissipation}
 \+ \\underbrace{\\tensor{D}}\_{diffusion}
 \+ \\underbrace{\\tensor{\\Omega}}\_{rotation}DtD​(R)\=productionP​​\+pressure−strainΠ​​−dissipationϵ​​\+diffusionD​​\+rotationΩ​​
Here, the production term P\\tensor{P}P is given by:

P\=−R ∙ (∇u\+(∇u)T) \\tensor{P}
 \=
 \- \\tensor{R} \\dprod \\left(\\grad \\u \+ \\left(\\grad \\u \\right)^T \\right)P\=−R∙(∇u\+(∇u)T)
All other terms on the r.h.s. require modelling.
