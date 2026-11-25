<!-- https://doc.openfoam.com/2606/tools/processing/solvers/algorithm-p-rgh -->

# Hydrostatic pressure effects

For cases that the hydrostatic pressure contribution

ρ(g ∙ h) \\rho ( \\vec{g} \\dprod \\vec{h} )ρ(g∙h)
is important, e.g. for buoyant and multiphase cases, it is numerically
convenient to solve for an alternative pressure defined by

p′\=p−ρ(g ∙ h). p' \= p \- \\rho ( \\vec{g} \\dprod \\vec{h} ).p′\=p−ρ(g∙h).
In OpenFOAM solver applications the p′p'p′ pressure term is named `p_rgh`.
The momentum equation

∂∂t(ρu)\+∇ ∙ (ρu⊗u)−∇ ∙ (μeff∇u)\=−∇p\+ρg \\ddt{\\rho \\u} \+ \\div ( \\rho \\u \\otimes \\u ) \- \\div ( \\mu\_{\\eff} \\grad \\u )
 \= \- \\grad p \+ \\rho \\vec{g}∂t∂​(ρu)\+∇∙(ρu⊗u)−∇∙(μeff​∇u)\=−∇p\+ρg
is transformed to use p′p'p′:

p′\=p−ρ(g ∙ h). p' \= p \- \\rho ( \\vec{g} \\dprod \\vec{h} ).p′\=p−ρ(g∙h).
After the following substitutions:

−p\=−p′−ρ(g ∙ h)−∇p\=−∇(p′)−∇(ρ(g ∙ h))\=−∇(p′)−ρg ∙ ∇h−h ∙ ∇(ρg)\=−∇(p′)−ρg ∙ I−g ∙ h∇(ρ)−\\cancelto0ρh ∙ ∇(g)\=−∇(p′)−ρg−g ∙ h∇ρ\\begin{aligned}
 \- p \& \= \- p' \- \\rho ( \\vec{g} \\dprod \\vec{h} ) \\\\
 \- \\grad p \& \= \- \\grad( p') \- \\grad ( \\rho ( \\vec{g} \\dprod \\vec{h} ) ) \\\\
 \& \= \- \\grad( p') \- \\rho \\vec{g} \\dprod \\grad \\vec{h} \- \\vec{h} \\dprod \\grad(\\rho \\vec{g}) \\\\
 \& \= \- \\grad( p') \- \\rho \\vec{g} \\dprod \\tensor{I} \- \\vec{g} \\dprod \\vec{h} \\grad (\\rho) \- \\cancelto{0}{\\rho \\vec{h} \\dprod \\grad (\\vec{g})} \\\\
 \& \= \- \\grad( p') \- \\rho \\vec{g} \- \\vec{g} \\dprod \\vec{h} \\grad \\rho
\\end{aligned}−p−∇p​\=−p′−ρ(g∙h)\=−∇(p′)−∇(ρ(g∙h))\=−∇(p′)−ρg∙∇h−h∙∇(ρg)\=−∇(p′)−ρg∙I−g∙h∇(ρ)−\\cancelto0ρh∙∇(g)\=−∇(p′)−ρg−g∙h∇ρ​
where, for CFD meshes the term ∇h\\grad \\vec{h}∇h is given by the gradient of
the cell centres, which equates to the tensor I\\tensor{I}I, the momentum
equation becomes:

∂∂t(ρu)\+∇ ∙ (ρu⊗u)−∇ ∙ (μeff∇u)\=−∇p′−g ∙ h∇ρ \\ddt{\\rho \\u} \+ \\div ( \\rho \\u \\otimes \\u ) \- \\div ( \\mu\_{\\eff} \\grad \\u )
 \= \- \\grad p' \- \\vec{g} \\dprod \\vec{h} \\grad \\rho∂t∂​(ρu)\+∇∙(ρu⊗u)−∇∙(μeff​∇u)\=−∇p′−g∙h∇ρ
For constant density applications this can be further simplified to

∂∂t(ρu)\+∇ ∙ (ρu⊗u)−∇ ∙ (μeff∇u)\=−∇p′ \\ddt{\\rho \\u} \+ \\div ( \\rho \\u \\otimes \\u ) \- \\div ( \\mu\_{\\eff} \\grad \\u )
 \= \- \\grad p'∂t∂​(ρu)\+∇∙(ρu⊗u)−∇∙(μeff​∇u)\=−∇p′
For examples of the use of this variable transformation, see:

* [Heat transfer](rtm/heat-transfer.md)
* [Multiphase](rtm/multiphase.md)
