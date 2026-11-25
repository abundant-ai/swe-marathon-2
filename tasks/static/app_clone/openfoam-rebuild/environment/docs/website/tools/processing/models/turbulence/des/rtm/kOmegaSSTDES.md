<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/des/rtm/kOmegaSSTDES -->

# k\-ω\-SST Detached Eddy Simulation (DES)

## Properties

* Two equation model for the turbulence kinetic energy, kkk, and
turbulence specific dissipation rate, ω\\omegaω.
* Based on the [k\-omega SST](../../ras/linear-evm/rtm/kOmegaSST.md) model

## Model equations

The turbulence specific dissipation rate equation is given by:

DDt(ρω)\=∇ ∙ (ρDω∇ω)\+ργGν−23ργω(∇ ∙ u)−ρβω2−ρ(F1−1)CDkω\+Sω, \\Ddt{\\rho \\omega}
 \=
 \\div \\left( \\rho D\_\\omega \\grad \\omega \\right)
 \+ \\rho \\gamma \\frac{G}{\\nu}
 \- \\frac{2}{3} \\rho \\gamma \\omega \\left( \\div \\u \\right)
 \- \\rho \\beta \\omega^2
 \- \\rho \\left( F\_1 \- 1 \\right) CD\_{k \\omega}
 \+ S\_\\omega,DtD​(ρω)\=∇∙(ρDω​∇ω)\+ργνG​−32​ργω(∇∙u)−ρβω2−ρ(F1​−1)CDkω​\+Sω​,
and the turbulence kinetic energy by:

DDt(ρk)\=∇ ∙ (ρDk∇k)\+min⁡(ρG,(c1β∗)ρkω)−23ρk(∇ ∙ u)−ρk1\.5d\~\+Sk. \\Ddt{\\rho k}
 \=
 \\div \\left( \\rho D\_k \\grad k \\right)
 \+ \\min\\left( \\rho G, \\left(c\_1 \\beta^{\*}\\right) \\rho k \\omega \\right)
 \- \\frac{2}{3} \\rho k \\left( \\div \\u \\right)
 \- \\rho \\frac{k^{1\.5}}{\\tilde{d}}
 \+ S\_k.DtD​(ρk)\=∇∙(ρDk​∇k)\+min(ρG,(c1​β∗)ρkω)−32​ρk(∇∙u)−ρd\~k1\.5​\+Sk​.
The length scale, d\~\\tilde{d}d\~, is given by:

min⁡(CDESΔ,kβ∗ω) \\min \\left(C\_{DES} \\Delta, \\frac{\\sqrt{k}}{\\beta^{\*} \\omega}\\right)min(CDES​Δ,β∗ωk​​)
The turbulence viscosity is obtained using:

νt\=a1kmax⁡(a1ω,b1F23S) \\nu\_t \= a\_1 \\frac{k}{\\max (a\_1 \\omega\_, b\_1 F\_{23} \\tensor{S})}νt​\=a1​max(a1​ω,​b1​F23​S)k​
## Default model coefficients

Base model coefficients:

| αk1\\alpha\_{k1}αk1​ | αk2\\alpha\_{k2}αk2​ | αω1\\alpha\_{\\omega 1}αω1​ | αω2\\alpha\_{\\omega 2}αω2​ | β1\\beta\_1β1​ | β2\\beta\_2β2​ | γ1\\gamma\_1γ1​ | γ2\\gamma\_2γ2​ |
| --- | --- | --- | --- | --- | --- | --- | --- |

```
0.85 |       1.0 |       0.5 |      0.856      |      0.075     |     0.0828   | 5/9 | 0.44

```

| β∗\\beta^{\*}β∗ | a1a\_1a1​ | b1b\_1b1​ | c1c\_1c1​ |
| --- | --- | --- | --- |

```
0.09 |      0.31 |       1.0 |     10.0

```

DES model coefficients:

| CDESkomCDESkomCDESkom | CDESkepsCDESkepsCDESkeps |
| --- | --- |

```
0.82   |            0.6

```

## Initialisation

## Usage

The model is specified using:

```
LES
{
    turbulence      on;
    LESModel        kOmegaSSTDES;
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

* [Foam::LESModels::kOmegaSSTDES](https://api.openfoam.com/2606/Foam_LESModels_kOmegaSSTDES.html)

References:

* *Strelets* [74](../../../../../../references.md#strelets_detached_2001)

See also:

* [Base k\-omega SST model](../../ras/linear-evm/rtm/kOmegaSST.md)
