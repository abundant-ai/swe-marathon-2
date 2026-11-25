<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/equation-of-state/ -->

# Equation of state

## Options

Equation of state model selections include:

* [Adiabatic perfect fluid](rtm/adiabaticPerfectFluid.md)
* [Boussinesq](rtm/Boussinesq.md)
* [Constant density](rtm/rhoConst.md)
* [Incompressible polynomial](rtm/icoPolynomial.md)
* [Incompressible tabulated](rtm/icoTabulated.md)
* [Linear](rtm/linear.md)
* [Peng\-Robinson gas](rtm/PengRobinsonGas.md)
* [Perfect fluid](rtm/perfectFluid.md)
* [Perfect gas](rtm/perfectGas.md)
* [Reciprocal polynomial](rtm/rPolynomial.md)

## Usage

The equation of state type is specified in the `thermoType` dictionary:

```
thermoType
{
    equationOfState     <model>;
    <...>
}

```

## Further information

Source code

* [grpSpecieEquationOfState](https://api.openfoam.com/2606/grpSpecieEquationOfState.html)
