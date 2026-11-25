<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/streamFunction -->

# streamFunction

## Description

The `streamFunction` function object computes the stream function, i.e.
<https://w.wiki/Ncm>.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `surfaceScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `pointScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `streamFunction` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
streamFunction1
{
    // Mandatory entries (unmodifiable)
    type            streamFunction;
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
| type | Type name: streamFunction | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func streamFunction

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [streamFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/streamFunction)

API:

* [Foam::functionObjects::streamFunction](https://api.openfoam.com/2606/Foam_functionObjects_streamFunction.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
