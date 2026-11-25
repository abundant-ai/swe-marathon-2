<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/ -->

# Schemes

## Introduction

OpenFOAM applications are designed for use with unstructured meshes, offering up
to second order accuracy, predominantly using collocated variable arrangements.
Most focus on the Finite Volume Method, for which the conservative form
of the general scalar transport equation for the property ϕ\\phiϕ takes the
form:

∂∂t(ρϕ)⏟unsteady\+∇ ∙ (ρϕu)⏟convection\=∇ ∙ (Γ∇ϕ)⏟diffusion\+Sϕ⏟source \\underbrace{\\ddt{\\rho \\phi}}\_{\\mathrm{unsteady}}
 \+ \\underbrace{\\div \\left(\\rho \\phi \\u \\right)}\_{\\mathrm{convection}}
 \= \\underbrace{\\div \\left(\\Gamma \\grad \\phi \\right)}\_{\\mathrm{diffusion}}
 \+ \\underbrace{S\_\\phi}\_{\\mathrm{source}}unsteady∂t∂​(ρϕ)​​\+convection∇∙(ρϕu)​​\=diffusion∇∙(Γ∇ϕ)​​\+sourceSϕ​​​
The Finite Volume Method requires the integration over a 3\-D control volume,
such that:

∫V∂∂t(ρϕ)dV\+∫V∇ ∙ (ρϕu)dV\=∫V∇ ∙ (Γ∇ϕ)dV\+∫VSϕdV \\int\_V \\ddt{\\rho \\phi} dV
 \+ \\int\_V \\div \\left(\\rho \\phi \\u \\right) dV
 \= \\int\_V \\div \\left(\\Gamma \\grad \\phi \\right) dV
 \+ \\int\_V S\_\\phi dV∫V​∂t∂​(ρϕ)dV\+∫V​∇∙(ρϕu)dV\=∫V​∇∙(Γ∇ϕ)dV\+∫V​Sϕ​dV
This equation is discretised to produce a system of algebraic equations of the
form

\[a11a12…a1na21a22…a2n⋮⋮⋱⋮an1an2…ann]\[x1x2⋮xn]\=\[b1b2⋮bn] \\begin{bmatrix}
 a\_{11} \& a\_{12} \& \\dots \& a\_{1n} \\\\
 a\_{21} \& a\_{22} \& \\dots \& a\_{2n} \\\\
 \\vdots \& \\vdots \& \\ddots \& \\vdots \\\\
 a\_{n1} \& a\_{n2} \& \\dots \& a\_{nn}
 \\end{bmatrix}
 \\begin{bmatrix}
 x\_{1} \\\\
 x\_{2} \\\\
 \\vdots \\\\
 x\_{n}
 \\end{bmatrix}
 \=
 \\begin{bmatrix}
 b\_{1} \\\\
 b\_{2} \\\\
 \\vdots \\\\
 b\_{n}
 \\end{bmatrix}​a11​a21​⋮an1​​a12​a22​⋮an2​​……⋱…​a1n​a2n​⋮ann​​​​x1​x2​⋮xn​​​\=​b1​b2​⋮bn​​​
or more concisely:

Ax\=b \\mat{A} \\vec{x} \= \\vec{b}Ax\=b
where:

A\\mat{A}A
: coefficient matrix

x\\vec{x}x
: vector of unknowns

b\\vec{b}b
: source vector

The discretisation process employs user selected schemes to build the
A\\mat{A}A matrix and b \\vec{b}b vector, described in the following
sections. Choice of schemes are set in the
[fvSchemes](../../../../fundamentals/case-structure/fvschemes.md) dictionary.

## Temporal schemes

OpenFOAM includes a variety of schemes to integrate fields with respect to time:

* [Time schemes](time/index.md)

## Spatial schemes

At their core, spatial schemes rely heavily on
[interpolation schemes](interpolation.md) to transform
cell\-based quantities to cell faces, in combination with
[Gauss Theorem](gauss-theorem.md) to
convert volume integrals to surface integrals.

* [Gradient schemes](gradient/index.md)
* [Divergence schemes](divergence/index.md)
* [Laplacian schemes](laplacian/index.md)
* [Surface\-normal gradient schemes](sngrad/index.md)

## Wall distance calculation method

Distance to the nearest wall is required, e.g. for a number of turbulence
models. Several calculation methods are available:

* [Wall distance calculation methods](wall-distance/index.md)

## Further information

* [Examples](examples.md)
* Further guidance on scheme usage, refer to the
[User Guide](http://www.openfoam.com/documentation/user-guide/fvSchemes.php).
* [Source documentation](https://api.openfoam.com/2606/grpFvSchemes.html)
