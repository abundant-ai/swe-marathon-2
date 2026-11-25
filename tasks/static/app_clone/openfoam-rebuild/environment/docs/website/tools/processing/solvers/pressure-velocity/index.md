<!-- https://doc.openfoam.com/2606/tools/processing/solvers/pressure-velocity/ -->

# Pressure\-velocity algorithms

noteThis page is under construction.

The background to the [SIMPLE](simple.md),
[PISO](piso.md) and
[PIMPLE](pimple.md) pressure\-velocity algorithms can be
demonstrated using the incompressible, inviscid flow equations, comprising the
**momentum equation**:

∂∂t(u)\+∇ ∙ (u⊗u)\=−∇p, \\ddt{\\u} \+ \\div (\\u \\otimes \\u) \= \- \\grad p,∂t∂​(u)\+∇∙(u⊗u)\=−∇p,
and **continuity equation**

∇ ∙ u\=0\. \\div \\u \= 0\.∇∙u\=0\.
Discretising the momentum equation leads to a set of algebraic equations of the
form:

M\[u]\=−∇p M\[\\u] \= \- \\grad pM\[u]\=−∇p
where the matrix M\[u]M\[\\u]M\[u] comprises the diagonal and off\-diagonal
contributions using the
decomposition:

M\[u]\=Au−H M\[\\u] \= A\\u \- \\vec{H}M\[u]\=Au−H
The
**discretised momentum equation** therefore becomes:

Au−H\=−∇p A\\u \- \\vec{H} \= \- \\grad pAu−H\=−∇p
which on re\-arranging leads to the
**velocity correction equation**:

u\=HA−1A∇p. \\u \= \\frac{\\vec{H}}{A} \- \\frac{1}{A} \\grad p.u\=AH​−A1​∇p.
The volumetric **flux corrector equation** is then derived by interpolating
u\\uu to the faces and dotting the result with the face area vectors,
Sf\\vec{S}\_fSf​:

ϕ\=uf ∙ Sf\=(HA)f ∙ Sf−(1A)fSf ∙ ∇f⊥p \\phi
 \= \\u\_f \\dprod \\vec{S}\_f
 \= \\left( \\frac{\\vec{H}}{A} \\right)\_f \\dprod \\vec{S}\_f
 \- \\left( \\frac{1}{A} \\right)\_f \\vec{S}\_f \\dprod \\snGrad pϕ\=uf​∙Sf​\=(AH​)f​∙Sf​−(A1​)f​Sf​∙∇f⊥​p
Discretisation of the continuity equation yields the
constraint:

∇ ∙ ϕ\=0\. \\div \\phi \= 0\.∇∙ϕ\=0\.
Substituting the flux equation leads to the
**pressure equation**:

∇ ∙ \[(1A)f∇p]\=∇ ∙ (HA)f. \\div \\left\[ \\left( \\frac{1}{A} \\right)\_f \\grad p \\right]
 \= \\div \\left( \\frac{\\vec{H}}{A} \\right)\_f.∇∙\[(A1​)f​∇p]\=∇∙(AH​)f​.
