<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/interfaceHeight -->

# interfaceHeight

## Description

The `interfaceHeight` function object reports the height of the interface above
a set of locations. For each location, it writes the vertical distance of the
interface above both the location and the lowest boundary. It also writes
the point on the interface from which these heights are computed. It uses
an integral approach, so if there are multiple interfaces above or below a
location then this method will generate average values.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file 1 | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/height` |
| output file 2 | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/position` |
| output field | \- | \- |

## Usage

Example of the `interfaceHeight` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
interfaceHeight1
{
    // Mandatory entries (unmodifiable)
    type            interfaceHeight;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    locations       ((0 0 0) (10 0 0) (20 0 0));

    // Optional entries (runtime modifiable)
    alpha           alpha.water;
    liquid          true;
    direction       (1 0 0);
    interpolationScheme    cellPoint;

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
| type | Type name: interfaceHeight | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| locations | Locations to report the height at | vectorList | yes | \- |
| alpha | Name of alpha field | word | no | alpha |
| liquid | Flag if the alpha field that of the liquid | bool | no | true |
| direction | Direction of interface | vector | no | g |
| interpolationScheme | Interpolation scheme | word | no | cellPoint |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [StefanProblem](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/multiphase/StefanProblem)

Source code:

* [interfaceHeight](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/interfaceHeight)

API:

* [Foam::functionObjects::interfaceHeight](https://api.openfoam.com/2606/Foam_functionObjects_interfaceHeight.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
