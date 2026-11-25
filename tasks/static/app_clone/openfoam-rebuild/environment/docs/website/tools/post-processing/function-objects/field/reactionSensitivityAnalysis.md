<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/reactionSensitivityAnalysis -->

# reactionSensitivityAnalysis

## Description

The `reactionsSensitivityAnalysis` function object
computes indicators for reaction rates of creation or destruction
of species in each reaction.

This function object creates four data files named:

```
"consumption"    :   consumption rate
"production"     :   destruction rate
"productionInt"  :   integral between dumps of the production rate
"consumptionInt" :   integral between dumps of the consumption rate

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `reactionsSensitivityAnalysis` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
reactionsSensitivityAnalysis1
{
    // Mandatory entries (unmodifiable)
    type            reactionsSensitivityAnalysis;
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
| type | Type name: reactionsSensitivityAnalysis | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

* Function object only applicable to single cell cases.
* Needs a `chemistryModel` chosen.

## Further information

Source code:

* [reactionSensitivityAnalysis](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/reactionSensitivityAnalysis)

API:

* [Foam::functionObjects::reactionsSensitivityAnalysis](https://api.openfoam.com/2606/Foam_functionObjects_reactionsSensitivityAnalysis.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
