<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/rtm/Euler -->

# Euler implicit time scheme

## Properties

* Implicit
* First order in time
* Transient
* Unconditionally stable for linear problems

## Discretisation

The Euler implicit scheme evaluates all terms at the new time level. For the temporal
derivative alone, on a static mesh with uniform time step Δt\\Delta tΔt, the rate is
represented as:

∂∂t(ϕ)≈ϕ−ϕoΔt \\ddt{\\phi} \\approx \\frac{\\phi \- \\old{\\phi}}{\\Delta t}∂t∂​(ϕ)≈Δtϕ−ϕo​
Unlike [Crank\-Nicolson](CrankNicolson.md), no auxiliary field is stored; the
discretisation uses only the current and old\-time field values.

### Implicit and explicit contributions

When `fvm::ddt(phi)` is used, the temporal term contributes to the linear system for
ϕ\\phiϕ as:

| Contribution | Discrete form |
| --- | --- |
| Implicit (matrix diagonal) | 1Δt V ϕ\\displaystyle\\frac{1}{\\Delta t}\\, V\\,\\phiΔt1​Vϕ |
| Explicit (source) | 1Δt ϕo V\\displaystyle\\frac{1}{\\Delta t}\\,\\old{\\phi}\\, VΔt1​ϕoV |

where VVV is the cell volume. The corresponding explicit evaluation from `fvc::ddt(phi)`
is the difference between these two parts.

## Usage

The scheme is specified using:

```
ddtSchemes
{
    default         Euler;
    ddt(phi)        Euler;
}

```

Euler implicit is the most robust first\-order scheme and forms the basis for
[Crank\-Nicolson](CrankNicolson.md) (with off\-centring coefficient α\=0\\alpha \= 0α\=0) and
the start\-up behaviour of higher\-order schemes. For second\-order accuracy in time,
consider [backward differencing](backward.md) or Crank\-Nicolson instead.

## Further information

Source code

* [Foam::fv::EulerDdtScheme](https://api.openfoam.com/2606/Foam_fv_EulerDdtScheme.html)
