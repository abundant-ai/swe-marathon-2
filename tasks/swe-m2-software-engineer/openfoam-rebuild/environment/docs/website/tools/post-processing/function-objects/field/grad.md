<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/grad -->

# grad

## Description

The `grad` function object computes
the gradient of an input field.

The operation is limited to scalar and vector volume or surface fields, and
the output is a volume vector or tensor field.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}{Scalar,Vector}Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol{Vector,Tensor}Field` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `grad` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
grad1
{
    // Mandatory entries (unmodifiable)
    type            grad;
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
| type | Type name: grad | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "grad(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [grad](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/grad)

API:

* [Foam::functionObjects::grad](https://api.openfoam.com/2606/Foam_functionObjects_grad.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
