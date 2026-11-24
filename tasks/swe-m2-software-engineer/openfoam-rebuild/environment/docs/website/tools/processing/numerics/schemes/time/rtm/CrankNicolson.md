<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/time/rtm/CrankNicolson -->

# Crank\-Nicolson time scheme

## Properties

* Implicit
* Second order in time (when the off\-centring coefficient is 1, after startup)
* Transient
* Off\-centring often required for stability on complex flows
* Boundedness not guaranteed

## Discretisation

Consider a generic transport equation for a scalar ϕ\\phiϕ:

∂∂t(ϕ)\+∇ ∙ (Uϕ)−∇2(Γϕ)\=S \\ddt{\\phi} \+ \\div \\left(\\vec U \\phi \\right) \- \\laplacian \\left(\\Gamma \\phi \\right) \= S∂t∂​(ϕ)\+∇∙(Uϕ)−∇2(Γϕ)\=S
Crank\-Nicolson evaluates terms at the mid\-point of the time step. OpenFOAM achieves this by
splitting each contribution into an **implicit** part that enters the linear system
(`fvm::` terms) and an **explicit** part that is carried forward from previous time
levels. For the temporal derivative alone, the scheme stores an auxiliary field
ddt0(ϕ)\\mathrm{ddt0}(\\phi)ddt0(ϕ) on the mesh registry.

On a static mesh, with uniform time step Δt\\Delta tΔt and off\-centring coefficient
α∈\[0,1]\\alpha \\in \[0, 1]α∈\[0,1], the temporal rate after startup is represented as:

∂∂t(ϕ)≈1\+αΔt(ϕ−ϕo)−ddt0(ϕ) \\ddt{\\phi} \\approx \\frac{1 \+ \\alpha}{\\Delta t}\\left(\\phi \- \\old{\\phi}\\right)
 \- \\mathrm{ddt0}(\\phi)∂t∂​(ϕ)≈Δt1\+α​(ϕ−ϕo)−ddt0(ϕ)
The field ddt0(ϕ)\\mathrm{ddt0}(\\phi)ddt0(ϕ) is updated each time step from the previous time levels:

ddt0(ϕ)\=1\+αΔt(ϕo−ϕoo)−α ddt0o(ϕ) \\mathrm{ddt0}(\\phi) \= \\frac{1 \+ \\alpha}{\\Delta t}
 \\left(\\old{\\phi} \- \\oldold{\\phi}\\right)
 \- \\alpha\\, \\mathrm{ddt0}\_{o}(\\phi)ddt0(ϕ)\=Δt1\+α​(ϕo−ϕoo)−αddt0o​(ϕ)
When α\=1\\alpha \= 1α\=1 the scheme is fully centred; when α\=0\\alpha \= 0α\=0 it reduces to the
[Euler implicit](Euler.md) scheme.

### Implicit and explicit contributions

When `fvm::ddt(phi)` is used, the temporal term contributes to the linear system for
ϕ\\phiϕ as:

| Contribution | Discrete form |
| --- | --- |
| Implicit (matrix diagonal) | 1\+αΔt V ϕ\\displaystyle\\frac{1 \+ \\alpha}{\\Delta t}\\, V\\,\\phiΔt1\+α​Vϕ |
| Explicit (source) | \[1\+αΔt ϕo\+ddt0(ϕ)]V\\displaystyle\\left\[\\frac{1 \+ \\alpha}{\\Delta t}\\,\\old{\\phi} \+ \\mathrm{ddt0}(\\phi)\\right] V\[Δt1\+α​ϕo\+ddt0(ϕ)]V |

where VVV is the cell volume. The corresponding explicit evaluation from `fvc::ddt(phi)`
is the difference between these two parts.

The implicit weighting of off\-centred terms is related to the off\-centring coefficient by:

cCN\=11\+α c\_{\\mathrm{CN}} \= \\frac{1}{1 \+ \\alpha}cCN​\=1\+α1​
On the first time step the scheme uses the Euler implicit coefficient 1/Δt1/\\Delta t1/Δt to
avoid start\-up problems; from the second step onward the (1\+α)/Δt(1 \+ \\alpha)/\\Delta t(1\+α)/Δt
formulation applies.

## Usage

The scheme is specified using:

```
ddtSchemes
{
    default         CrankNicolson <coeff>
    ddt(phi)        CrankNicolson <coeff>;
}

```

The mandatory `<coeff>` is the off\-centring coefficient α\\alphaα in the range \[0,1]\[0, 1]\[0,1]:

* 0: equivalent to [Euler implicit](Euler.md)
* 1: fully centred Crank\-Nicolson
* Values such as 0\.9 are commonly used as a compromise between accuracy and robustness

The coefficient may also be specified as a `Function1` to ramp from Euler to
Crank\-Nicolson over an initial period, for example:

```
ddtSchemes
{
    default         CrankNicolson
    ocCoeff
    {
        type        scale;
        scale       linearRamp;
        duration    0.01;
        value       0.9;
    };
}

```

Compared with the [backward](backward.md) scheme, Crank\-Nicolson requires only the
current and old\-time field values (not old\-old\-time values in the matrix assembly), but
is generally less robust. The backward scheme provides formal second\-order accuracy with
stronger stability characteristics.

## Further information

Source code

* [Foam::fv::CrankNicolsonDdtScheme](https://api.openfoam.com/2606/Foam_fv_CrankNicolsonDdtScheme.html)

Reference

* *Crank and Nicolson* [11](../../../../../../references.md#crank_practical_1947)
