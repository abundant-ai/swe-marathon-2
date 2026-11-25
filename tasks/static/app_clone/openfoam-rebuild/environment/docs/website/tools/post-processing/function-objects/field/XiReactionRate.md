<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/XiReactionRate -->

# XiReactionRate

## Description

The `XiReactionRate` function object writes the turbulent flame\-speed and
reaction\-rate volScalarFields for the Xi\-based combustion models.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/{St,wdot}` |

## Usage

Example of the `XiReactionRate` function object by using `functions`
sub\-dictionary in `system/controlDict` file:

```
XiReactionRate1
{
    // Mandatory entries (unmodifiable)
    type            XiReactionRate;
    libs            (fieldFunctionObjects);

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
| type | Type name: XiReactionRate | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [annularCombustorTurbine](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/XiDyMFoam/annularCombustorTurbine)

Source code:

* [XiReactionRate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/XiReactionRate)

API:

* [Foam::functionObjects::XiReactionRate](https://api.openfoam.com/2606/Foam_functionObjects_XiReactionRate.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
