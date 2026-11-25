<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/ -->

# Linear eddy viscosity models

Linear eddy viscosity turbulence model selections include:

* [k\-kl\-ω](rtm/kkLOmega.md)
* [k\-ε](rtm/kEpsilon.md)
* [k\-ε\-φ\-f](rtm/kEpsilonPhitF.md)
* [k\-ω Shear Stress Transport (SST)](rtm/kOmegaSST.md)
* [Langtry\-Menter k\-ω Shear Stress Transport (SST)](rtm/kOmegaSSTLM.md)
* [Lien\-Leschziner](rtm/LienLeschziner.md)
* [q\-ζ](rtm/qZeta.md)
* [Realizable k\-ε](rtm/realizableKEpsilon.md)
* [RNG k\-ε](rtm/RNGkEpsilon.md)
* [Spalart\-Allmaras](rtm/SpalartAllmaras.md)

## Background

Under the Boussinesq hypothesis [7](../../../../../../references.md#boussinesq_essai_1877), the deviatoric
anisotropic stress is considered proportional to the traceless mean rate of
strain:

−ρRdev\=−ρu′⊗u′‾\+23ρkI\=μt\[2 S−(23∇ ∙ u)I] \- \\rho \\tensor{R}\_\\mathit{dev}
 \=
 \- \\rho \\av{\\u' \\otimes \\u'} \+ \\frac{2}{3} \\rho k \\tensor{I}
 \=
 \\mu\_t \\left\[ 2\\, \\tensor{S} \- \\left( \\frac{2}{3} \\div \\u \\right) \\tensor{I} \\right]−ρRdev​\=−ρu′⊗u′​\+32​ρkI\=μt​\[2S−(32​∇∙u)I]
where S\\tensor{S}S is the symmetric tensor

S\=12(∇u‾\+∇(u‾)T) \\tensor{S} \= \\frac{1}{2}\\left( \\grad \\av{\\u} \+ \\grad \\left( \\av{\\u} \\right)^T \\right)S\=21​(∇u\+∇(u)T)
leading to:

−ρRdev\=μt(∇u‾\+∇(u‾)T)\+μt(23∇ ∙ u)I \- \\rho \\tensor{R}\_\\mathit{dev}
 \=
 \\mu\_t \\left( \\grad \\av{\\u} \+ \\grad \\left( \\av{\\u} \\right)^T \\right)
 \+ \\mu\_t \\left( \\frac{2}{3} \\div \\u \\right)\\tensor{I}−ρRdev​\=μt​(∇u\+∇(u)T)\+μt​(32​∇∙u)I
where μt\\mu\_tμt​ is the dynamic *eddy viscosity*. The momentum equation
therefore becomes:

∂∂t(ρu‾)\+∇ ∙ (ρu‾⊗u‾)\=g−∇p‾′\+∇ ∙ (μeff∇u‾)\+∇ ∙ \[μeff dev2((∇u‾)T)] \\ddt{\\rho \\av{\\u}}
 \+ \\div \\left( \\rho \\av{\\u} \\otimes \\av{\\u} \\right)
 \=
 \\vec{g}
 \- \\grad \\av{p}'
 \+ \\div \\left( \\mu\_\\mathit{eff} \\grad \\av{\\u} \\right)
 \+ \\div \\left\[ \\mu\_\\mathit{eff} \\, \\mathrm{dev2}\\left(\\left(\\grad \\av{\\u}\\right)^T \\right) \\right]∂t∂​(ρu)\+∇∙(ρu⊗u)\=g−∇p​′\+∇∙(μeff​∇u)\+∇∙\[μeff​dev2((∇u)T)]
where μeff\\mu\_\\mathit{eff}μeff​ is the *effective* dynamic eddy viscosity:

μeff\=μ\+μt \\mu\_\\mathit{eff} \= \\mu \+ \\mu\_tμeff​\=μ\+μt​
i.e. the sum of the laminar and turbulent contributions.
