<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/polynomial -->

# Polynomial

Dynamic viscosity, μ\\muμ \[Pa.s]

μ\=∑i\=1N(ciTi−1)\\mu \= \\sum\_{i\=1}^N \\left( c\_i T^{i\-1} \\right)μ\=i\=1∑N​(ci​Ti−1)
Thermal conductivity, κ\\kappaκ \[W/mK]

κ\=∑i\=1N(ciTi−1)\\kappa \= \\sum\_{i\=1}^N \\left( c\_i T^{i\-1} \\right)κ\=i\=1∑N​(ci​Ti−1)
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=κcp\\alpha\_h \= \\frac{\\kappa}{c\_p}αh​\=cp​κ​
## Usage

The `polynomial` transport model is defined using the entries:

```
transport
{
    muCoeffs<8>     ( <c1> <c2> <c3> <c4> <c5> <c6> <c7> <c8> );
    kappaCoeffs<8>  ( <c1> <c2> <c3> <c4> <c5> <c6> <c7> <c8> );
}

```

Where

* `muCoeffs<8>` : Polynomial coefficients (x8\)
* `kappaCoeffs<8>` : Polynomial coefficients (x8\)

## Further information

Source code

* [polynomial](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/polynomial)
