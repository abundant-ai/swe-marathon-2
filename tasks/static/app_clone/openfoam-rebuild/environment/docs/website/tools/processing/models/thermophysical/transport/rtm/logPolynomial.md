<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/logPolynomial -->

# Log polynomial

Dynamic viscosity, μ\\muμ \[Pa.s]

ln⁡(μ)\=∑i\=1N(ciln⁡(T)i−1)\\ln(\\mu) \= \\sum\_{i\=1}^N \\left( c\_i \\ln(T)^{i\-1} \\right)ln(μ)\=i\=1∑N​(ci​ln(T)i−1)
Thermal conductivity, κ\\kappaκ \[W/mK]

ln⁡(κ)\=∑i\=1N(ciln⁡(T)i−1)\\ln(\\kappa) \= \\sum\_{i\=1}^N \\left( c\_i \\ln(T)^{i\-1} \\right)ln(κ)\=i\=1∑N​(ci​ln(T)i−1)
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=κcp\\alpha\_h \= \\frac{\\kappa}{c\_p}αh​\=cp​κ​
## Usage

The `logPolynomial` transport model is defined using the entries:

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

* [logPolynomial](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/logPolynomial)
