<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/sutherland -->

# Sutherland

Transport model based on the work of Sutherland
[75](../../../../../../references.md#sutherland_viscosity_1893).

Dynamic viscosity, μ\\muμ \[Pa.s]

μ\=AsT1\+Ts/T\\mu \= A\_s \\frac{\\sqrt{T}}{1 \+ T\_s/T}μ\=As​1\+Ts​/TT​​
Thermal conductivity, κ\\kappaκ \[W/mK]

κ\=μcv(1\.32\+1\.77Rcv)\\kappa \= \\mu c\_v \\left( 1\.32 \+ 1\.77 \\frac{R}{c\_v} \\right)κ\=μcv​(1\.32\+1\.77cv​R​)
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=κcp\\alpha\_h \= \\frac{\\kappa}{c\_p}αh​\=cp​κ​
## Usage

The `sutherland` transport model is defined using the entries:

```
transport
{
    As              <scalar>;
    Ts              <scalar>;
}

```

Where

* `As` : Model coefficient \[]
* `Ts` : Model coefficient \[K]

For example, for air:

```
transport
{
    As          1.4792e-06;
    Ts          116;
}

```

## Further information

Source code

* [sutherland](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/sutherland)
