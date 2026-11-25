<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/processorField -->

# processorField

## Description

The `processorField` function object
writes a scalar field whose value is the local processor ID.
The output field name is `processorID`.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `processorField` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
processorField1
{
    // Mandatory entries (unmodifiable)
    type            processorField;
    libs            (fieldFunctionObjects);

    // Optional (inherited) entries
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
| type | Type name: processorField | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Example by using the `postProcess` utility:

```
postProcess -func processorField

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)
* [aeroFoil](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/overSimpleFoam/aeroFoil)
* [motorBike\_leakDetection](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/snappyHexMesh/motorBike_leakDetection)

Source code:

* [processorField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/processorField)

API:

* [Foam::functionObjects::processorField](https://api.openfoam.com/2606/Foam_functionObjects_processorField.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
