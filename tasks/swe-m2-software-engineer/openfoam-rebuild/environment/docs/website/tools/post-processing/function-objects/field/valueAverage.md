<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/valueAverage -->

# valueAverage

## Description

The `valueAverage` function object
computes the ensemble\- or time\-based singular\-value average values,
with optional windowing, from the output of function objects
that generate non\-field type values, e.g. `Cd` of `forceCoeffs` or
`momentum_x` in `momentum` function objects.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `valueAverage` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
valueAverage1
{
    // Mandatory entries (unmodifiable)
    type              valueAverage;
    libs              (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    functionObject    <FO>;                       // forceCoeffs1;
    fields            (<field1> ... <fieldN>);    // (Cm Cd Cl);

    // Optional entries (runtime modifiable)
    resetOnRestart    false;
    window            0.5;

    // Optional (inherited) entries
    writePrecision    8;
    writeToFile       true;
    useUserTime       true;
    region            region0;
    enabled           true;
    log               true;
    timeStart         0;
    timeEnd           1000;
    executeControl    timeStep;
    executeInterval   1;
    writeControl      timeStep;
    writeInterval     1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: valueAverage | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| functionObject | Name of function object to retrieve data | word | yes | \- |
| fields | Names of operand fields | wordList | yes | \- |
| resetOnRestart | Reset the averaging on restart | bool | no | false |
| window | Averaging window | scalar | no | VGREAT |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Sample output

Text reporting:

* Average value, e.g. using drag coefficient, `Cd`, retrieved from
a [forceCoeffs](../forces/forceCoeffs.md) function object:

```
CdMean: 0.3

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<field-name>Mean` : average value

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [valueAverage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/valueAverage)

API:

* [Foam::functionObjects::valueAverage](https://api.openfoam.com/2606/Foam_functionObjects_valueAverage.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
