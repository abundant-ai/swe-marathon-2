<!-- https://doc.openfoam.com/2606/tools/processing/solvers/transport-eqns/momentum-transport -->

# Momentum transport equation

The momentum transport equation is as follows:

∂ρu∂t\+∇ ∙ (uu)\+fMRF(ρ,u)\+∇ ∙ R\=−∇prgh−(g⋅h−(gh)ref)∇ρ\+Sρ,u \\frac{\\partial \\rho \\u}{\\partial t}
 \+ \\div (\\u \\u)
 \+ f\_{MRF}(\\rho, \\u)
 \+ \\div \\vec{R}
 \=
 \- \\grad p\_{rgh}
 \- (\\vec{g} \\cdot \\vec{h} \- (\\vec{gh})\_{\\ref}) \\grad \\rho
 \+ \\vec{S}\_{\\rho, \\u}∂t∂ρu​\+∇∙(uu)\+fMRF​(ρ,u)\+∇∙R\=−∇prgh​−(g⋅h−(gh)ref​)∇ρ\+Sρ,u​
where:

| Property | Description |
| --- | --- |
| ttt | Time |
| ρ\\rhoρ | Density |
| u\\uu | Velocity |
| fMRFf\_{MRF}fMRF​ | Multiple reference frame function |
| R\\vec{R}R | Stress tensor |
| prghp\_{rgh}prgh​ | Pressure excluding the hydrostatic contribution |
| h\\vec{h}h | Spatial coordinates |
| g\\vec{g}g | Gravitational acceleration |
| ghref\\vec{gh}\_{ref}ghref​ | Reference hydrostatic pressure |
| S\\vec{S}S | Source term through `fvOption` |

The pressure\-term transformation involving the
hydrostatic contribution is explained as follows:

* [Hydrostatic pressure effects](../algorithm-p-rgh.md)
