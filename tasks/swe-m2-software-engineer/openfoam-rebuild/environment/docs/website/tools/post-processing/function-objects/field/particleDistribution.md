<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/particleDistribution -->

# particleDistribution

## Description

The `particleDistribution` function object
generates a particle distribution for lagrangian data at a given time.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `particleDistribution` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
particleDistribution1
{
    // Mandatory entries (unmodifiable)
    type        particleDistribution;
    libs        (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    cloud       <cloudName>;
    nameVsBinWidth
    (
        (d 0.1)
        (U 10)
    );
    setFormat   raw;

    // Optional entries (runtime modifiable)
    tagField    none;

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
| type | Type name: particleDistribution | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| cloud | Name of cloud to process | word | yes | \- |
| nameVsBinWidth | List of cloud field\-bin width | wordHashTable | yes | \- |
| setFormat | Output format | word | yes | \- |
| tagField | Name of cloud field to use group particles | word | no | none |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [aachenBomb](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/sprayFoam/aachenBomb)

Source code:

* [particleDistribution](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/particleDistribution)

API:

* [Foam::functionObjects::particleDistribution](https://api.openfoam.com/2606/Foam_functionObjects_particleDistribution.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
