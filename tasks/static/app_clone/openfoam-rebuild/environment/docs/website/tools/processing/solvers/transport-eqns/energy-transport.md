<!-- https://doc.openfoam.com/2606/tools/processing/solvers/transport-eqns/energy-transport -->

# Energy transport equation

The energy transport equation based on enthalpy is given as follows:

∂ρh∂t\+∇ ∙ (ρuh)\+∂ρK∂t\+∇ ∙ (ρuK)−∂p∂t−∇ ∙ (αeff∇h)\=ρu⋅g\+frad(h)\+Sρ,h \\frac{\\partial \\rho h}{\\partial t}
 \+ \\div (\\rho \\u h)
 \+ \\frac{\\partial \\rho K}{\\partial t}
 \+ \\div (\\rho \\u K)
 \- \\frac{\\partial p}{\\partial t}
 \- \\div (\\alpha\_{eff} \\grad h)
 \=
 \\rho \\u \\cdot \\vec{g}
 \+ f\_{rad}(h)
 \+ \\vec{S}\_{\\rho, h}∂t∂ρh​\+∇∙(ρuh)\+∂t∂ρK​\+∇∙(ρuK)−∂t∂p​−∇∙(αeff​∇h)\=ρu⋅g\+frad​(h)\+Sρ,h​
The energy transport equation based on internal energy is given as follows:

∂ρe∂t\+∇ ∙ (ρue)\+∂ρK∂t\+∇ ∙ (ρuK)\+∇ ∙ (pu)−∇ ∙ (αeff∇e)\=ρu⋅g\+frad(e)\+Sρ,e \\frac{\\partial \\rho e}{\\partial t}
 \+ \\div (\\rho \\u e)
 \+ \\frac{\\partial \\rho K}{\\partial t}
 \+ \\div (\\rho \\u K)
 \+ \\div (p \\u)
 \- \\div (\\alpha\_{eff} \\grad e)
 \=
 \\rho \\u \\cdot \\vec{g}
 \+ f\_{rad}(e)
 \+ \\vec{S}\_{\\rho, e}∂t∂ρe​\+∇∙(ρue)\+∂t∂ρK​\+∇∙(ρuK)\+∇∙(pu)−∇∙(αeff​∇e)\=ρu⋅g\+frad​(e)\+Sρ,e​
where:

| Property | Description |
| --- | --- |
| ttt | Time |
| ρ\\rhoρ | Density |
| hhh | Enthalpy |
| eee | Internal energy |
| u\\uu | Velocity |
| KKK | Kinetic energy |
| ppp | Pressure |
| αeff\\alpha\_{eff}αeff​ | Effective thermal diffusivity |
| g\\vec{g}g | Gravitational acceleration |
| fradf\_{rad}frad​ | Radiation function |
| S\\vec{S}S | Source term through `fvOption` |
