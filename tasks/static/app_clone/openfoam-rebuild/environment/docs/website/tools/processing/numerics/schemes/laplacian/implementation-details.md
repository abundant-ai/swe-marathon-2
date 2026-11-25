<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/laplacian/implementation-details -->

# Implementation details

For a cell with volume VVV, Gauss' theorem is applied to give:

∇ ∙ (Γ∇ϕ)\=1V∫V∇ ∙ (Γ∇ϕ)dV\=1V∮SΓ∇ϕdS\=1V∑inFace(∇ϕ)f,i ∙ ΓfSf,i \\div \\left( \\Gamma \\grad \\phi \\right)
 \= \\frac{1}{V}\\int\_V \\div \\left( \\Gamma \\grad \\phi \\right)dV
 \= \\frac{1}{V} \\oint\_S \\Gamma \\grad \\phi d\\vec{S}
 \= \\frac{1}{V} \\sum\_i^{\\mathrm{nFace}}\\left(\\grad{\\phi}\\right)\_{f,i} \\dprod \\Gamma\_f \\vec{S}\_{f,i}∇∙(Γ∇ϕ)\=V1​∫V​∇∙(Γ∇ϕ)dV\=V1​∮S​Γ∇ϕdS\=V1​i∑nFace​(∇ϕ)f,i​∙Γf​Sf,i​
i.e. the laplacian is given by the sum over all faces of the dot product of
the face normal with the gradient value at the face. To transform the quantity
from the cell centre to the face centre, an
[interpolation scheme](../interpolation/index.md) is required.

See
