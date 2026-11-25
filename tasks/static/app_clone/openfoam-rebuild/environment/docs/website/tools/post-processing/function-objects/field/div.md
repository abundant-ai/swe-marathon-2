<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/div -->

# div

## Description

The `div` function object computes the divergence of an input field.

To execute `div` function object on an input `<field>`, a numerical scheme
should be defined for `div(<field>)` in `system/fvSchemes.divSchemes`.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | {surfaceScalar,volVector}Field | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | volScalarField | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `div` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
div1
{
    // Mandatory entries (unmodifiable)
    type            div;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
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
| type | Type name: div | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "div(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [div](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/div)

API:

* [Foam::functionObjects::div](https://api.openfoam.com/2606/Foam_functionObjects_div.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
