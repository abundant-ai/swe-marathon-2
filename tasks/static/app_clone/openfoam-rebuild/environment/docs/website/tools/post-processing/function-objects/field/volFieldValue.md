<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/volFieldValue -->

# volFieldValue

## Description

The `volFieldValue` function object provides options to manipulate
volume field data into derived forms, e.g. to report summations, averages and
extrema.

Operations:

* `none` : no operation
* `sum` : summation
* `sumMag` : sum of magnitude
* `average`: average
* `weightedAverage`: weighted average
* `volAverage`: volume average
* `weightedVolAverage`: weighted volume average
* `volIntegrate`: volume integral
* `min`: minimum
* `max`: maximum
* `CoV`: coefficient of variation

## Usage

Example of the `volFieldValue` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
volFieldValue1
{
    // Mandatory entries (unmodifiable)
    type            volFieldValue;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);
    operation       <operationType>;
    regionType      <volRegion>;

    // Optional entries (runtime modifiable)
    postOperation   none;
    weightField     alpha1;

    // Optional (inherited) entries
    writeFields     false;
    scalingFactor   1.0;
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
| type | Type name: surfaceFieldValue | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of operand fields | wordList | yes | \- |
| regionType | Face regionType: see below | word | yes | \- |
| name | Name for regionType | word | yes | \- |
| operation | Operation type: see below | word | yes | \- |
| postOperation | Post\-operation type: see below | word | no | none |
| weightField | Name of field to apply weighting | word | no | none |

The inherited entries are elaborated in:

* [fieldValue](fieldValue.md)

Options for the `regionType` entry:

```
cellZone     | requires a 'name' entry to specify the cellZone
all          | all cells

```

Options for the `operation` entry:

```
none                 | No operation
min                  | Minimum
max                  | Maximum
sum                  | Sum
sumMag               | Sum of component magnitudes
average              | Ensemble average
volAverage           | Volume weighted average
volIntegrate         | Volume integral
CoV                  | Coefficient of variation: standard deviation/mean
weightedSum          | Weighted sum
weightedAverage      | Weighted average
weightedVolAverage   | Weighted volume average
weightedVolIntegrate | Weighted volume integral

```

Options for the `postOperation` entry:

```
none          | No additional operation after calculation
mag           | Component-wise `mag()` after normal operation
sqrt          | Component-wise `sqrt()` after normal operation

```

Usage by the `postProcess` utility is not available.

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<operation-type>(<region-name>, <field-name>)` : result

## Further information

Tutorial:

* [twoSimpleRotors](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/overRhoPimpleDyMFoam/twoSimpleRotors)
* [poolEvaporation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/icoReactingMultiphaseInterFoam/poolEvaporation)

Source code:

* [volFieldValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldValues/volFieldValue)

API:

* [Foam::functionObjects::fieldValues::volFieldValue](https://api.openfoam.com/2606/Foam_functionObjects_fieldValues_volFieldValue.html)

Related:

* [surfaceFieldValue](surfaceFieldValue.md)
function object
* [fieldValueDelta](../../../../index.md#function-objects-field-fieldvaluedelta) function
object

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0)
