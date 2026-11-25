<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/yPlus -->

# yPlus

## Description

The `yPlus` function object computes the near wall y1\+y\_1^\+y1\+​ for turbulence
models.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `yPlus` function object by using `functions` sub\-dictionary in
`system/controlDict` file:

```
yPlus1
{
    // Mandatory entries (unmodifiable)
    type            yPlus;
    libs            (fieldFunctionObjects);

    // Optional (inherited) entries
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
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
| type | Type name: yPlus | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Example by using the `postProcess` utility:

```
<solver> -postProcess -func yPlus

```

## Further information

Tutorial:

* [pimpleFoam](../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `cylinder2D` tutorial:
[cylinder2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/cylinder2D)

Source code:

* [yPlus](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/yPlus)

API:

* [Foam::functionObjects::yPlus](https://api.openfoam.com/2606/Foam_functionObjects_yPlus.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+) ]
