<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/WLF -->

# Williams\-Landel\-Ferry

Transport model based on the work of Williams et. al.
[89](../../../../../../references.md#williams_temperature_1955).

Dynamic viscosity, μ\\muμ \[Pa.s]

μ\=μ0exp⁡(−C1(T−Tr)C2\+T−Tr)\\mu \= \\mu\_0 \\exp \\left( \- \\frac{C\_1 ( T \- T\_r )}{C\_2 \+ T \- T\_r} \\right)μ\=μ0​exp(−C2​\+T−Tr​C1​(T−Tr​)​)
Thermal conductivity, κ\\kappaκ \[W/mK]

κ\=cpμPr\\kappa \= \\frac{c\_p \\mu}{Pr}κ\=Prcp​μ​
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=μPr\\alpha\_h \= \\frac{\\mu}{Pr}αh​\=Prμ​
## Usage

The `WLF` transport model is defined using the entries:

```
transport
{
    mu0             <scalar>;
    Tr              <scalar>;
    C1              <scalar>;
    C2              <scalar>;
    Pr              <scalar>;
}

```

Where

* `mu0` : Dynamic viscosity at the reference temperature \[Pa.s]
* `Tr` : Reference temperature \[K]
* `C1` : Model coefficient \[]
* `C2` : Model coefficient \[K]
* `Pr` : Prandtl number

## Further information

Source code

* [WLF](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/WLF)
