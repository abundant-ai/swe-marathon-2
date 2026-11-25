<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/DESModelRegions -->

# DESModelRegions

## Description

The `DESModelRegions` function object computes an indicator field for
detached eddy simulation (DES) turbulence calculations, where the values
the indicator mean:

```
0 = Reynolds-averaged Navier-Stokes (RAS) regions
1 = Large eddy simulation (LES) regions

```

The `DESModelRegions` function object can only be executed for DES simulations.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | volScalarField | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `DESModelRegions` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
DESModelRegions1
{
    // Mandatory entries (unmodifiable)
    type            DESModelRegions;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    result          DESField;

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
| type | Type name: DESModelRegions | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| result | Name of DES indicator field | word | no | `<FO>` |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [pimpleFoam](../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `surfaceMountedCube`
tutorial: [fullCase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/surfaceMountedCube/fullCase)

Source code:

* [DESModelRegions](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/DESModelRegions)

API:

* [Foam::functionObjects::DESModelRegions](https://api.openfoam.com/2606/Foam_functionObjects_DESModelRegions.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
