<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/rtm/tabulated -->

# Tabulated

Dynamic viscosity, μ\\muμ \[Pa.s]

μ\=f(p,T)\\mu \= f(p, T)μ\=f(p,T)
Thermal conductivity, κ\\kappaκ \[W/mK]

κ\=f(p,T)\\kappa \= f(p, T)κ\=f(p,T)
Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

αh\=κcp\\alpha\_h \= \\frac{\\kappa}{c\_p}αh​\=cp​κ​
## Usage

The `tabulated` transport model is defined using the entries:

```
transport
{
    mu
    (
        (<T0>     <mu0>)
        (<T1>     <mu1>)
        (<T2>     <mu2>)
        ...
        (<TN>     <muN>)
    );

    kappa
    (
        (<T0>     <kappa0>)
        (<T1>     <kappa1>)
        (<T2>     <kappa2>)
        ...
        (<TN>     <kappaN>)
    );
}

```

Where

* `mu` : List of tuples of (temperature viscosity) values describing the dynamic
viscosity table
* `kappa` : List of tuples of (temperature conductivity) values describing the
thermal conductivity table

## Further information

Source code

* [sutherland](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/specie/transport/sutherland)
