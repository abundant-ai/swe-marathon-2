<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/const -->

# Constant

Dynamic viscosity, $$ \\mu £$ \[Pa.s]

μ\=μ0\\mu \= \\mu\_0μ\=μ0​
Thermal conductivity, κ\\kappaκ \[W/mK]

κ\=cpμPr\\kappa \= \\frac{c\_p \\mu}{Pr}κ\=Prcp​μ​
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=μPr\\alpha\_h \= \\frac{\\mu}{Pr}αh​\=Prμ​
## Usage

The `const` transport model is defined using the entries:

```
transport
{
    mu              <scalar>;
    Pr              <scalar>;
}

```

Where

* `mu` : dynamic viscosity \[Pa.s]
* `Pr` : Prandtl number \[\-]

## Further information

Source code

* [const](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/const)
