<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/rtm/kEqn -->

# k equation

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
## Default model coefficients

| CeC\_eCe​ | CkC\_kCk​ |
| --- | --- |

```
1.048 |      0.094

```

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        kEqn;
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

* [Foam::LESModels::kEqn](https://api.openfoam.com/2606/Foam_LESModels_kEqn.html)

References:

* *Yoshizawa* [91](../../../../../../references.md#yoshizawa_statistical_1986)
