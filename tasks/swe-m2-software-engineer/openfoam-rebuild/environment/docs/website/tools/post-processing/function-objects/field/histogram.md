<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/histogram -->

# histogram

## Description

The `histogram` function object computes
the volume\-weighted histogram of an input `volScalarField`.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | volScalarField | `$FOAM_CASE/<time>/<inpField>` |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

The set written contains two columns, the first the volume averaged values,
the second the raw bin count.

## Usage

Example of the `histogram` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
histogram1
{
    // Mandatory entries (unmodifiable)
    type            histogram;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries (runtime modifiable)
    field       p;
    nBins       100;
    setFormat   gnuplot;

    // Optional entries (runtime modifiable)
    max         5;
    min        -5;

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
| type | Type name: histogram | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of operand field | word | yes | \- |
| nBins | Number of histogram bins | label | yes | \- |
| setFormat | Output format | word | yes | \- |
| max | Maximum value sampled | scalar | no | fieldMax |
| min | minimum value sampled | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

If `max` is not provided it will use the field's min and max as the bin
extremes. If `max` is provided but not `min`, it will use 0\.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [histogram](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/histogram)

API:

* [Foam::functionObjects::histogram](https://api.openfoam.com/2606/Foam_functionObjects_histogram.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
