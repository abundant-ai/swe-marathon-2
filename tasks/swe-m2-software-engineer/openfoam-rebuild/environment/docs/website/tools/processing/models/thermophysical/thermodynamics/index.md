<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/thermodynamics/ -->

# Thermodynamics

The thermodynamics model is responsible for evaluating:

* Specific heat capacity at constant pressue, cpc\_pcp​ \[J/kg/k]
* Absolute enthalpy, HaH\_aHa​ \[J/kg]
* Sensible enthalpy, HsH\_sHs​ \[J/kg]
* Chemical enthalpy, HcH\_cHc​ \[J/kg/K]
* Entropy, SSS \[J/kg]
* Gibbs free energy at the standard state, GstdG\_{\\std}Gstd​, \[J/kg]

## Options

Equation of state model selections include:

* [Constant (energy)](rtm/eConst.md)
* [Constant (enthalpy)](rtm/hConst.md)
* [JANAF](rtm/janaf.md)
* [Polynomial (enthalpy)](rtm/hPolynomial.md)
* [Power (enthalpy)](rtm/hPower.md)
* [Tabulated (enthalpy)](rtm/hTabulated.md)

## Usage

The thermodynamics type is specified in the `thermoType` dictionary:

```
thermoType
{
    thermodynamics      <model>;
    <...>
}

```
