<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence -->

# Divergence schemes

The divergence of a property QQQ describes the net rate at which it
changes as a function of space, represented using the notation:

∇ ∙ Q \\div Q∇∙Q
If QQQ is a vector quantity, this equates to

∇ ∙ Q\=∂Qx∂x\+∂Qy∂y\+∂Qz∂z \\div \\vec{Q}
 \= \\frac{\\partial Q\_x}{\\partial x}
 \+ \\frac{\\partial Q\_y}{\\partial y}
 \+ \\frac{\\partial Q\_z}{\\partial z}∇∙Q\=∂x∂Qx​​\+∂y∂Qy​​\+∂z∂Qz​​
## Usage

Divergence schemes are specified in the [fvSchemes](../../../../fundamentals/case-structure/fvschemes.md)
file under the `divSchemes` sub\-dictionary using the general syntax:

```
divSchemes
{
    default         none;
    div(Q)          Gauss <interpolation scheme>;
}

```

A typical use is for convection schemes, which transport a property, QQQ
under the influence of a velocity field ϕ\\phiϕ, specified using:

```
divSchemes
{
    default         none;
    div(phi,Q)      Gauss <interpolation scheme>;
}

```

The `phi` keyword is typically used to represent the flux (flow) across cell
faces, i.e.

* volumetric flux: ϕ\=uf ∙ Sf\\phi \= \\u\_f \\dprod \\vec{S}\_fϕ\=uf​∙Sf​
* mass flux: ϕ\=ρf(uf ∙ Sf)\\phi \= \\rho\_f \\left( \\u\_f \\dprod \\vec{S}\_f \\right)ϕ\=ρf​(uf​∙Sf​)

## Options

### NVD/TVD convection schemes

Many of the convection schemes available in OpenFOAM are based on the TVD and NVD \[PROVIDE REF]
For further information, see the page [schemes\-divergence\-nvdtvd](../../../../index.md#schemes-divergence-nvdtvd)

* [Limited linear divergence scheme](divergence/rtm/limitedLinear.md)
* [Linear divergence scheme](divergence/rtm/linear.md)
* [Linear\-upwind divergence scheme](divergence/rtm/linearUpwind.md)
* [Mid\-point divergence scheme](divergence/rtm/midPoint.md)
* [Minmod divergence scheme](divergence/rtm/Minmod.md)
* [MUSCL divergence scheme](divergence/rtm/MUSCL.md)
* [QUICK divergence scheme](divergence/rtm/QUICK.md)
* [UMIST divergence scheme](divergence/rtm/UMIST.md)
* [Upwind divergence scheme](divergence/rtm/upwind.md)
* [Van Leer divergence scheme](divergence/rtm/vanLeer.md)

### Non\-NVD/TVD convection schemes

* [Courant number blended divergence scheme](divergence/rtm/CoBlended.md)
* [DES hybrid divergence scheme](divergence/rtm/DEShybrid.md)
* [Filtered Linear (2\) divergence scheme](divergence/rtm/filteredLinear2.md)
* [LUST divergence scheme](divergence/rtm/LUST.md)

## Special cases

Several options are available for convection schemes for certain flow cases,
including for steady state, bounded scalar transport and limited schemes.

### Steady state

For steady state cases the `bounded` form can be applied:

```
divSchemes
{
    default         none;
    div(phi,Q)      bounded Gauss <interpolation scheme>;
}

```

This adds a linearised, implicit source contribution to the transport equation
of the form

∂∂t(u)\+∇ ∙ (u⊗u)−(∇ ∙ u)u\=∇ ∙ (Γ∇u)\+Su \\ddt{\\u}
 \+ \\div (\\u \\otimes \\u )
 \- \\color{red}{( \\div \\u ) \\u}
 \= \\div ( \\Gamma \\grad \\u )
 \+ S\_u∂t∂​(u)\+∇∙(u⊗u)−(∇∙u)u\=∇∙(Γ∇u)\+Su​
i.e. it removes a component proportional to the continuity error. This acts as
a convergence aid to tend towards a bounded solution as the calculation
proceeds. At convergence, this term becomes zero and does not contribute to
the final solution.

### Bounded scalars

The `limited<interpolation scheme>` options bound scalar field values to
user\-specified limits, e.g. for the
[Van Leer divergence scheme](divergence/rtm/vanLeer.md) scheme

```
limitedVanLeer -1 3

```

Many fields require bounding between 0 and 1, for which the following syntax
is used:

```
<interpolation scheme>01

```

### V schemes

A set of schemes for vector fields where the limiter is applied in the
direction of greatest change.

## Example

See [this example](divergence/example.md) to see the
relative performance of the schemes.

## Further information

See the [Implementation details](divergence/implementation-details.md)
"implementation details" to see how the schemes are coded.
