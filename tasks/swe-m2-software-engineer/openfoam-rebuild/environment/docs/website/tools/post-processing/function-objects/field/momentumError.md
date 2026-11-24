<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/momentumError -->

# momentumError

## Description

The `momentumError` function object
computes balance terms for the steady momentum equation.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | `volVectorField` | `$FOAM_CASE/<time>/<file>` |

## Usage

Example of the `momentumError` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
momentumError1
{
    // Mandatory entries (unmodifiable)
    type            momentumError;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    p               <pName>;
    U               <UName>;
    phi             <phiName>;

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
| type | Type name: momentumError | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| p | Name of pressure field | word | no | p |
| U | Name of velocity field | word | no | U |
| phi | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [airFoil2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/airFoil2D)

Source code:

* [momentumError](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/momentumError)

API:

* [Foam::functionObjects::momentumError](https://api.openfoam.com/2606/Foam_functionObjects_momentumError.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
