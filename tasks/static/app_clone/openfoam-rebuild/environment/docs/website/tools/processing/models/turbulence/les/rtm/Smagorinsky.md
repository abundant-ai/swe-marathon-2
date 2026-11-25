<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/les/rtm/Smagorinsky -->

# Smagorinsky

## Properties

## Model equations

The turbulence viscosity is given by:

νt\=CkΔk0\.5 \\nu\_t \= C\_k \\Delta k^{0\.5}νt​\=Ck​Δk0\.5
where the turbulence kinetic energy is given by the solution of the quadratic
equation:

ak2\+bk\+c\=0 a k^2 \+ b k \+ c \= 0ak2\+bk\+c\=0
The coefficients are:

a\=CeΔb\=23tr(D)c\=2CkΔ(dev(D) ∙∙ D) \\begin{aligned}
 a \&\= \\frac{C\_e}{\\Delta} \\\\
 b \&\= \\frac{2}{3} \\mathrm{tr} (\\tensor{D}) \\\\
 c \&\= 2 C\_k \\Delta \\left( \\mathrm{dev}(\\tensor{D}) \\ddprod \\tensor{D} \\right)
 \\end{aligned}abc​\=ΔCe​​\=32​tr(D)\=2Ck​Δ(dev(D)∙∙D)​
and

D\=12(∇u\+∇(u)T) \\tensor{D} \= \\frac{1}{2} \\left( \\grad \\u \+ \\grad (\\u)^T \\right)D\=21​(∇u\+∇(u)T)
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
    LESModel        Smagorinsky;
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

* [Foam::LESModels::Smagorinsky](https://api.openfoam.com/2606/Foam_LESModels_Smagorinsky.html)

References:

* *Smagorinsky* [64](../../../../../../references.md#smagorinsky_general_1963)
