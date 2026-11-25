<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/readFields -->

# readFields

## Description

The `readFields` function object
reads fields from the time directories and adds them to the mesh database
for further post\-processing.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | Mesh database |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `readFields` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
readFields1
{
    // Mandatory entries (unmodifiable)
    type            readFields;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields      (<field1> <field2> ... <fieldN>);

    // Optional entries (runtime modifiable)
    readOnStart true;

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
| type | Type name: readFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of the operand fields | wordList | yes | \- |
| readOnStart | Flag to start reading on start\-up | bool | no | true |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)
* [externalCoupledSquareBendLiq](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/externalCoupledSquareBendLiq)

Source code:

* [readFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/readFields)

API:

* [Foam::functionObjects::readFields](https://api.openfoam.com/2606/Foam_functionObjects_readFields.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
