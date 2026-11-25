<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/rtm/dynamicKEqn -->

# Dynamic k equation

## Properties

## Model equations

The turbulence kinetic energy equation is given by:

DDt(ρk)\=∇ ∙ (ρDk∇k)\+ρG−23ρk∇ ∙ u−Ceρk1\.5Δ\+Sk \\Ddt{\\rho k}
 \=
 \\div \\left( \\rho D\_k \\grad k \\right)
 \+ \\rho G
 \- \\frac{2}{3} \\rho k \\div \\u
 \- \\frac{C\_e \\rho k^{1\.5}}{\\Delta}
 \+ S\_kDtD​(ρk)\=∇∙(ρDk​∇k)\+ρG−32​ρk∇∙u−ΔCe​ρk1\.5​\+Sk​
The CeC\_eCe​ and CkC\_kCk​ coefficients are derived from local flow
properties.

## Default model coefficients

None

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        dynamicKEqn;
}

```

## Boundary conditions

Inlet

* [fixedValue](../../../../boundary-conditions/rtm/derived/general/fixedValue.md)

Outlet

* [Constrained outlet](../../../../boundary-conditions/rtm/derived/inletOutlet/inletOutlet.md)

Walls

* wall functions

## Further information

Source code:

* [Foam::LESModels::dynamicKEqn](https://api.openfoam.com/2606/Foam_LESModels_dynamicKEqn.html)

References:

* *Kim and Menon* [27](../../../../../../references.md#kim_new_1995)
