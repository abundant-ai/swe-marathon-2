<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/enstrophy -->

# enstrophy

## Description

The `enstrophy` function object computes the enstrophy of an input
`volVectorField`.

Enstrophy, i.e. ξ\\xiξ:

ξ\=0\.5∣∇×u∣2 \\xi \= 0\.5 \\mag{\\nabla \\times \\u}^2ξ\=0\.5∣∇×u∣2
where u\\uu is the input `volVectorField`.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | volVectorField | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | volScalarField | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `enstrophy` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
enstrophy1
{
    // Mandatory entries (unmodifiable)
    type            enstrophy;
    libs            (fieldFunctionObjects);

    // Optional (inherited) entries
    field           <inputField>;
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
| type | Type name: enstrophy | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func enstrophy

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [enstrophy](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/enstrophy)

API:

* [Foam::functionObjects::enstrophy](https://api.openfoam.com/2606/Foam_functionObjects_enstrophy.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
