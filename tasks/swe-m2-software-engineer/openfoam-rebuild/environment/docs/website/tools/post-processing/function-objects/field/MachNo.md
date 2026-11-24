<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/MachNo -->

# MachNo

## Description

The `MachNo` function object computes the Mach number as a `volScalarField`.

The Mach number is a dimensionless quantity representing the ratio of flow
velocity past a boundary to the local speed of sound:

M\=∣u∣γp/ρ M \= \\frac{\|\\u\|}{\\sqrt{\\gamma p/\\rho}}M\=γp/ρ​∣u∣​
where:

MMM
: Mach number

u\\uu
: Velocity

γ\\gammaγ
: The ratio of specific heat of a gas at a constant pressure to heat at a constant volume

ppp
: Static pressure

ρ\\rhoρ
: Fluid density

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `MachNo` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
MachNo1
{
    // Mandatory entries (unmodifiable)
    type            MachNo;
    libs            (fieldFunctionObjects);

    // Optional (inherited) entries
    field           <inpField>;
    result          <fieldResult>;
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
| type | Type name: MachNo | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func MachNo

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [MachNo](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/MachNo)

API:

* [Foam::functionObjects::MachNo](https://api.openfoam.com/2606/Foam_functionObjects_MachNo.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
