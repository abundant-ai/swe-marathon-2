<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras -->

# Reynolds Averaged Simulation (RAS)

## Options

OpenFOAM includes Reynolds Averaged Simulation turbulence closures based on
linear and non\-linear eddy viscosity models, and Reynolds stress transport
models.

* [Linear eddy viscosity models](ras/linear-evm/index.md)
* [Non\-linear eddy viscosity models](ras/nonlinear-evm/index.md)
* [Reynolds stress transport models](ras/rstm/index.md)

## Usage

RAS is selected by setting the `simulationType` entry

```
simulationType  RAS;

RAS
{
    // Model input parameters
}

```

Suitable for:

* 1\-D, 2\-D and 3\-D cases
* steady\-state or transient

## Initialisation

Care should be taken to provide an adequate initialisation of turbulence fields.
For open systems, the flow can evolve via the inlets. However, note that the
initial field values should be approximate for the flow medium, where
non\-physical levels will result in non\-physical turbulence viscosity
predictions and case instability.

Appropriate formulae and/or methods are provided in the documentation for
each model.

## Background

Reynolds decomposition of the velocity into its mean and fluctuating
contributions takes the form

u(x,t)\=u‾(x,t)\+u′(x,t) \\u(\\vec{x}, t)
 \= \\av{\\u}(\\vec{x}, t) \+ \\u'(\\vec{x}, t)u(x,t)\=u(x,t)\+u′(x,t)
where the mean of the fluctuating component is defined as zero:

u′‾\=0\\av{\\u'} \= 0u′\=0

Applied to the Navier Stokes equations, this leads to equations for the mean
velocity and pressure:

∂∂t(ρ)\+∇ ∙ (ρu‾)\=0 \\ddt{\\rho} \+ \\div \\left(\\rho \\av{\\u} \\right) \= 0∂t∂​(ρ)\+∇∙(ρu)\=0
∂∂t(ρu‾)\+∇ ∙ (ρu‾⊗u‾)\=g\+∇ ∙ (τ)‾−∇ ∙ (ρR) \\ddt{\\rho \\av{\\u}}
 \+ \\div \\left( \\rho \\av{\\u} \\otimes \\av{\\u} \\right)
 \=
 \\vec{g}
 \+ \\div \\av{\\tensor(\\tau)}
 \- \\div \\left( \\rho \\tensor{R} \\right)∂t∂​(ρu)\+∇∙(ρu⊗u)\=g\+∇∙(τ)​−∇∙(ρR)
where the averaged stress tensor, τ‾\\av{\\tau}τ, for Newtonian fluids is
given by:

τ‾\=−(p\+23μ∇ ∙ u‾)I\+μ(∇u‾\+(∇u‾)T) \\av{\\tensor{\\tau}}
 \=
 \- \\left(p \+ \\frac{2}{3}\\mu \\div \\av{\\u} \\right) \\tensor{I}
 \+ \\mu \\left(\\grad \\av{\\u} \+ \\left(\\grad \\av{\\u} \\right)^T \\right)τ\=−(p\+32​μ∇∙u)I\+μ(∇u\+(∇u)T)
Using the relationship:

∇ ∙ u‾\=tr(∇u‾)\=tr((∇u‾)T) \\div \\av{\\u}
 \= \\mathrm{tr} \\left( \\grad \\av{\\u} \\right)
 \= \\mathrm{tr} \\left( \\left( \\grad \\av{\\u} \\right)^T \\right)∇∙u\=tr(∇u)\=tr((∇u)T)
the stress tensor becomes:

τ‾\=−pI\+μ\[∇u‾\+(∇u‾)T−23tr((∇u‾)T)I]\=−pI\+μ\[∇u‾\+dev2((∇u‾)T)] \\av{\\tensor{\\tau}}
 \=
\- p \\tensor{I}
 \+ \\mu \\left\[\\grad \\av{\\u} \+ \\left( \\grad \\av{\\u} \\right)^T \- \\frac{2}{3} \\mathrm{tr} \\left( \\left( \\grad \\av{\\u} \\right)^T \\right) \\tensor{I} \\right]
 \=
\- p \\tensor{I}
 \+ \\mu \\left\[\\grad \\av{\\u} \+ \\mathrm{dev2} \\left( \\left( \\grad \\av{\\u} \\right)^T \\right) \\right]τ\=−pI\+μ\[∇u\+(∇u)T−32​tr((∇u)T)I]\=−pI\+μ\[∇u\+dev2((∇u)T)]
and the dev2\\mathrm{dev2}dev2 operator is defined as:

dev2(ϕ)\=ϕ−23tr(ϕ)I \\mathrm{dev2}\\left(\\phi\\right)
 \=
 \\phi \- \\frac{2}{3} \\mathrm{tr} \\left(\\phi\\right) \\tensor{I}dev2(ϕ)\=ϕ−32​tr(ϕ)I
R\\tensor{R}R, is the *Reynolds stress tensor*

R\=u′⊗u′‾\\tensor{R} \= \\av{\\u' \\otimes \\u'}R\=u′⊗u′​

The Reynolds stress tensor is further divided into isotropic and deviatoric
anisotropic contributions:

R\=u′⊗u′‾\=23kI⏟isotropic\+u′⊗u′‾−23kI⏟deviatoric \\tensor{R}
 \= \\av{\\u' \\otimes \\u'}
 \= \\underbrace{\\frac{2}{3}k \\tensor{I}}\_{\\mathrm{isotropic}}
 \+ \\underbrace{\\av{\\u' \\otimes \\u'} \- \\frac{2}{3}k \\tensor{I}}\_{\\mathrm{deviatoric}}R\=u′⊗u′​\=isotropic32​kI​​\+deviatoricu′⊗u′​−32​kI​​
where kkk is the turbulent kinetic energy, defined by

k\=12u′ ∙ u′‾\=12tr(R) k \= \\frac{1}{2} \\av{\\u' \\dprod \\u'}
 \= \\frac{1}{2} \\mathrm{tr}\\left( \\tensor{R} \\right)k\=21​u′∙u′\=21​tr(R)
Only the anisotropic contribution of the Reynolds stress tensor transports
momentum, whereby the isotropic contribution can be added to the mean
pressure, leading to the full form:

∂∂t(ρu‾)\+∇ ∙ (ρu‾⊗u‾)\=g−∇p‾′\+∇ ∙ (μ∇u‾)\+∇ ∙ \[μ dev2((∇u‾)T)]−∇ ∙ (ρRdev) \\ddt{\\rho \\av{\\u}}
 \+ \\div \\left( \\rho \\av{\\u} \\otimes \\av{\\u} \\right)
 \=
 \\vec{g}
 \- \\grad \\av{p}'
 \+ \\div \\left( \\mu \\grad \\av{\\u} \\right)
 \+ \\div \\left\[ \\mu \\, \\mathrm{dev2}\\left(\\left(\\grad \\av{\\u}\\right)^T \\right) \\right]
 \- \\div \\left( \\rho \\tensor{R}\_\\mathit{dev} \\right)∂t∂​(ρu)\+∇∙(ρu⊗u)\=g−∇p​′\+∇∙(μ∇u)\+∇∙\[μdev2((∇u)T)]−∇∙(ρRdev​)
where

Rdev\=u′⊗u′‾−23kI \\tensor{R}\_\\mathit{dev}
 \= \\av{\\u' \\otimes \\u'} \- \\frac{2}{3}k \\tensor{I}Rdev​\=u′⊗u′​−32​kI
and

p‾′\=p‾\+23ρk\\av{p}' \= \\av{p} \+ \\frac{2}{3} \\rho kp​′\=p​\+32​ρk

The RAS family of turbulence models provide methods to approximate the
deviatoric anisotropic stress contribution due to Rdev\\tensor{R}\_\\mathit{dev}Rdev​.

## Wall modelling

* See: [Wall functions](ras/wall-functions/index.md)

## Further information

Source code:

* [RAS](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/RAS)
* [wallFunctions](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/wallFunctions)

Related:

* [Source documentation](https://api.openfoam.com/2606/grpRASTurbulence.html)
