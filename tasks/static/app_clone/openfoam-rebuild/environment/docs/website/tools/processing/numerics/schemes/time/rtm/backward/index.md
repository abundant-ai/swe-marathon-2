<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/rtm/backward/ -->

# Backward time scheme

## Properties

* Implicit
* Second order in time
* Transient
* Boundedness not guaranteed
* Conditionally stable

## Discretisation

The backward scheme uses second\-order backward differencing in time, requiring the
current and two previous time\-level field values. On a static mesh with uniform time
step Δt\\Delta tΔt, the temporal rate is represented as:

∂∂t(ϕ)≈1Δt(32ϕ−2ϕo\+12ϕoo) \\ddt{\\phi} \\approx \\frac{1}{\\Delta t}
 \\left(\\frac{3}{2}\\phi \- 2\\old{\\phi} \+ \\frac{1}{2}\\oldold{\\phi}\\right)∂t∂​(ϕ)≈Δt1​(23​ϕ−2ϕo\+21​ϕoo)
For non\-uniform time steps, OpenFOAM uses the general coefficients coefft\\mathrm{coeff}\_tcoefft​,
coefft0\\mathrm{coeff}\_{t0}coefft0​ and coefft00\\mathrm{coeff}\_{t00}coefft00​ derived from Δt\\Delta tΔt and the
previous step size Δto\\Delta t^{o}Δto:

∂∂t(ϕ)≈1Δt(coefft ϕ−coefft0 ϕo\+coefft00 ϕoo) \\ddt{\\phi} \\approx \\frac{1}{\\Delta t}
 \\left(
 \\mathrm{coeff}\_t\\,\\phi
 \- \\mathrm{coeff}\_{t0}\\,\\old{\\phi}
 \+ \\mathrm{coeff}\_{t00}\\,\\oldold{\\phi}
 \\right)∂t∂​(ϕ)≈Δt1​(coefft​ϕ−coefft0​ϕo\+coefft00​ϕoo)
where

coefft\=1\+ΔtΔt\+Δto,coefft00\=Δt2Δto(Δt\+Δto),coefft0\=coefft\+coefft00 \\mathrm{coeff}\_t \= 1 \+ \\frac{\\Delta t}{\\Delta t \+ \\Delta t^{o}}, \\quad
 \\mathrm{coeff}\_{t00} \= \\frac{\\Delta t^{2}}{\\Delta t^{o}\\left(\\Delta t \+ \\Delta t^{o}\\right)}, \\quad
 \\mathrm{coeff}\_{t0} \= \\mathrm{coeff}\_t \+ \\mathrm{coeff}\_{t00}coefft​\=1\+Δt\+ΔtoΔt​,coefft00​\=Δto(Δt\+Δto)Δt2​,coefft0​\=coefft​\+coefft00​
On the first time step the scheme reduces to [Euler implicit](../Euler.md) until two
previous time levels are available.

### Implicit and explicit contributions

When `fvm::ddt(phi)` is used, the temporal term contributes to the linear system for
ϕ\\phiϕ as:

| Contribution | Discrete form |
| --- | --- |
| Implicit (matrix diagonal) | coefftΔt V ϕ\\displaystyle\\frac{\\mathrm{coeff}\_t}{\\Delta t}\\, V\\,\\phiΔtcoefft​​Vϕ |
| Explicit (source) | 1Δt(coefft0 ϕo−coefft00 ϕoo)V\\displaystyle\\frac{1}{\\Delta t}\\left(\\mathrm{coeff}\_{t0}\\,\\old{\\phi} \- \\mathrm{coeff}\_{t00}\\,\\oldold{\\phi}\\right) VΔt1​(coefft0​ϕo−coefft00​ϕoo)V |

where VVV is the cell volume. The corresponding explicit evaluation from `fvc::ddt(phi)`
is the difference between these two parts.

## Usage

The scheme is specified using:

```
ddtSchemes
{
    default         backward;
    ddt(phi)        backward;
}

```

Compared with [Crank\-Nicolson](../CrankNicolson.md), the backward scheme is generally
more robust and provides formal second\-order accuracy in time, but requires
old\-old\-time field values in the matrix assembly and does not offer the same
opportunity for flux limiting at the mid\-point of the time step.

## Further information

Source code

* [Foam::fv::backwardDdtScheme](https://api.openfoam.com/2606/Foam_fv_backwardDdtScheme.html)
