<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/ddt -->

# ddt

## Description

The `ddt` function object computes the Eulerian
time derivative of an input volume field for time\-variant simulations
(not appropriate to steady\-state simulations).

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `ddt` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
ddt1
{
    // Mandatory entries (unmodifiable)
    type            ddt;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries (runtime modifiable)
    field           <field>;

    // Optional (inherited) entries
    result          <fieldResult>;
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
| type | Type name: ddt | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "ddt(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [ddt](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/ddt)

API:

* [Foam::functionObjects::ddt](https://api.openfoam.com/2606/Foam_functionObjects_ddt.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
