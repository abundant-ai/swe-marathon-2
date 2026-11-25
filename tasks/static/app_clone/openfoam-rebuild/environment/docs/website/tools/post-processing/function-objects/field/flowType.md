<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/flowType -->

# flowType

## Description

The `flowType` function object computes
the flow type indicator of an input velocity field.

The flow type indicator is obtained according to the following equation:

λ\=∣D∣−∣Ω∣∣D∣\+∣Ω∣ \\lambda \= \\frac{\\mag{\\tensor D} \- \\mag{\\tensor \\Omega}}{ \\mag{\\tensor D} \+ \\mag{\\tensor \\Omega}}λ\=∣D∣\+∣Ω∣∣D∣−∣Ω∣​
where

λ\\lambdaλ
: Flow type indicator

D\\tensor DD
: Symmetric part of the gradient tensor of velocity

Ω\\tensor \\OmegaΩ
: Skew\-symmetric part of the gradient tensor of velocity

The flow type indicator values mean:

\-1
: rotational flow

0
: simple shear flow

1
: planar extensional flow

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `flowType` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
flowType1
{
    // Mandatory entries (unmodifiable)
    type            flowType;
    libs            (fieldFunctionObjects);

    // Optional (inherited) entries
    field           <field>;
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
| type | Type name: flowType | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func flowType

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [flowType](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/flowType)

API:

* [Foam::functionObjects::flowType](https://api.openfoam.com/2606/Foam_functionObjects_flowType.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
