<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldMinMax -->

# fieldMinMax

## Description

The `fieldMinMax` function object computes the values and locations of field
minima and maxima.
These are good indicators of calculation performance, e.g. to confirm that
predicted results are within expected bounds, or how well a case is converging.

Multiple fields can be processed, where for rank \> 0 primitives, e.g. vectors
and tensors, the extrema can be calculated per component, or by magnitude. In
addition, spatial location and local processor index are included in the output.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `fieldMinMax` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
fieldMinMax1
{
    // Mandatory entries (unmodifiable)
    type        fieldMinMax;
    libs        (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    mode        magnitude;
    fields      (<field1> <field2> ... <fieldN>);

    // Optional entries (runtime modifiable)
    location    true;

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
| type | Type name: fieldMinMax | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | List of operand fields | wordRes | yes | \- |
| location | Write location of the min/max value | bool | no | true |
| mode | Calculation mode: magnitude or component | word | no | magnitude |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `min(<field>)` : Minimum field value
* `min(<field>)_cell` : Minimum field value cell
* `min(<field>)_position` : Minimum field value position
* `min(<field>)_processor` : Minimum field value processor
* `max(<field>)` : Maximum field value
* `max(<field>)_cell` : Maximum field value cell
* `max(<field>)_position` : Maximum field value position
* `max(<field>)_processor` : Maximum field value processor

## Further information

Tutorial:

* [twoPhasePachuka](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/MPPICInterFoam/twoPhasePachuka)
* [turbulentFlatPlate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/turbulentFlatPlate)
* [externalCoupledSquareBendLiq](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/externalCoupledSquareBendLiq)

Source code:

* [fieldMinMax](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldMinMax)

API:

* [Foam::functionObjects::fieldMinMax](https://api.openfoam.com/2606/Foam_functionObjects_fieldMinMax.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+) ]
