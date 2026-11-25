<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/wallHeatFlux -->

# wallHeatFlux

## Description

The `wallHeatFlux` function object computes the wall\-heat flux at selected wall
patches.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<field>` |
| output field | `volScalarField` (only boundaryField) | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `wallHeatFlux` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
wallHeatFlux1
{
    // Mandatory entries (unmodifiable)
    type            wallHeatFlux;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    patches     (<patch1> ... <patchN>); // (wall1 "(wall2|wall3)");
    qr          qr;

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
| type | Type name: wallHeatFlux | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| patches | Names of operand patches | wordList | no | all wall patches |
| qr | Name of radiative heat flux field | word | no | qr |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Example by using the `postProcess` utility:

```
<solver> -postProcess -func wallHeatFlux

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `min(<patch-name>)` : minimum patch value
* `max(<patch-name>)` : maximum patch value
* `int(<patch-name>)` : integral patch value

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [Foam::functionObjects::wallHeatFlux](https://api.openfoam.com/2606/Foam_functionObjects_wallHeatFlux.html)

API:

* [wallHeatFlux](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/wallHeatFlux)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
