<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/divergence/implementation-details -->

# Implementation details

For a cell with volume VVV, Gauss' theorem is applied to give:

∇ ∙ u\=1V∫V(∇ ∙ u)dV\=1V∮S(n ∙ u)dS\=1V∑inFaceuf,i ∙ Sf,i \\div \\u
 \= \\frac{1}{V}\\int\_V \\left( \\div \\u \\right) dV
 \= \\frac{1}{V} \\oint\_S \\left( \\vec{n} \\dprod \\u \\right) d\\vec{S}
 \= \\frac{1}{V} \\sum\_i^{\\mathrm{nFace}}\\u\_{f,i} \\dprod \\vec{S}\_{f,i}∇∙u\=V1​∫V​(∇∙u)dV\=V1​∮S​(n∙u)dS\=V1​i∑nFace​uf,i​∙Sf,i​
i.e. the divergence is given by the sum over all faces of the dot product of
the face normal with the vector quantity at the face. To transform the quantity
from the cell centre to the face centre, an
[interpolation scheme](../interpolation.md) is required.

The divergence term contributions enter the system of equations via the owner
and neighbour cells (see gaussConvectionScheme.C)

```
fvm.lower() = -weights.internalField()*faceFlux.internalField();
fvm.upper() = fvm.lower() + faceFlux.internalField();
fvm.negSumDiag();

```

The overall weights www are derived from the selected scheme weights,
Ψ\\PsiΨ, and the linear wlw\_lwl​ interpolation weights, such that for a
positive flux:

w\=wlΨ\+(1−Ψ)u w \= w\_l \\Psi \+ (1 \- \\Psi)\_uw\=wl​Ψ\+(1−Ψ)u​
where the subscript ()u()\_u()u​ denotes the upwind contribution. The face
values are then calculated as:

ϕf\=ϕN\+w(ϕP−ϕN) \\phi\_f \= \\phi\_N \+ w \\left(\\phi\_P \- \\phi\_N \\right)ϕf​\=ϕN​\+w(ϕP​−ϕN​)
Source code:

* [Foam::limitedSurfaceInterpolationScheme](https://api.openfoam.com/2606/Foam_limitedSurfaceInterpolationScheme.html)
