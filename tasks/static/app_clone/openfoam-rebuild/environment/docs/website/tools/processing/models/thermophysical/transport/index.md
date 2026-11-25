<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/transport/ -->

# Transport

The transport model is responsible for evaluating:

* Dynamic viscosity, μ\\muμ \[Pa.s]
* Thermal conductivity, κ\\kappaκ \[W/mK]
* Thermal diffusivity, αh\\alpha\_hαh​ \[kg/ms]

## Options

Equation of state model selections include:

* [Constant](rtm/const.md)
* [Log polynomial](rtm/logPolynomial.md)
* [Sutherland](rtm/sutherland.md)
* [Tabulated](rtm/tabulated.md)

## Usage

The transport type is specified in the `thermoType` dictionary:

```
thermoType
{
    transport       <model>;
    <...>
}

```

## Further information

Source code

* [grpSpecieEquationOfState](https://api.openfoam.com/2606/grpSpecieEquationOfState.html)
