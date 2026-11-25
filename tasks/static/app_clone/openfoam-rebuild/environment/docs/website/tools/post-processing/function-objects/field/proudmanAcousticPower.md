<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/proudmanAcousticPower -->

# proudmanAcousticPower

## Description

The `proudmanAcousticPower` function object
computes the acoustic power due to the volume of isotropic turbulence
using Proudman's formula.

The acoustic power, i.e. PAP\_APA​ \[W/m^3] in terms of turbulent kinetic energy,
i.e. kkk, and turbulent kinetic energy dissipation rate, i.e. ϵ\\epsilonϵ
is given as:

PA\=αϵρϵMt5 P\_A \= \\alpha\_\\epsilon \\rho \\epsilon M\_t^5PA​\=αϵ​ρϵMt5​
where αϵ\=0\.1\\alpha\_\\epsilon \= 0\.1αϵ​\=0\.1 is a constant and

Mt\=2ka0 M\_t \= \\frac{\\sqrt{2 k}}{a\_0}Mt​\=a0​2k​​
with a0a\_0a0​ the speed of sound.

The acoustic power is also output in `dB` using:

LP\=10log⁡PAPref L\_P \= 10 \\log \\frac{P\_A}{P\_{\\ref}}LP​\=10logPref​PA​​
where Pref\=1e−12P\_{\\ref} \= 1e^{\-12}Pref​\=1e−12 \[W/m^3] is a constant.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `proudmanAcousticPower` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
proudmanAcousticPower1
{
    // Mandatory entries (unmodifiable)
    type            proudmanAcousticPower;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    alphaEps    0.1;
    // For incompressible flow simulations
    rhoInf      1.225;
    aRef        340;

    // Optional (inherited) entries
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: proudmanAcousticPower | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| rhoInf | Freestream density (for incompressible) | scalar | conditional | \- |
| aRef | Speed of sound (incompressible) | scalar | conditional | \- |
| alphaEps | Empirical model coefficient | scalar | no | 0\.1 |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

The freestream density and reference speed of sound are only necessary
when a thermodynamics package is unavailable, typically for incompressible
cases.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [proudmanAcousticPower](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/proudmanAcousticPower)

API:

* [Foam::functionObjects::proudmanAcousticPower](https://api.openfoam.com/2606/Foam_functionObjects_proudmanAcousticPower.html)

**History:** Introduced in version [v1912](https://www.openfoam.com/news/main-news/openfoam-v1912)
