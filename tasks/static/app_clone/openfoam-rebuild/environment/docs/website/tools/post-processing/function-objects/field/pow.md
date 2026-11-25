<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/pow -->

# pow

## Description

The `pow` function object computes the power of an input `volScalarField`.

f\=sf0n\+t f \= s f\_0^n \+ tf\=sf0n​\+t
where
fff
: Output `volScalarField`

f0f\_0f0​
: Input `volScalarField`

nnn
: Exponent

sss
: Scaling factor

ttt
: Offset factor

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volScalarField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `pow` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
pow1
{
    // Mandatory entries (unmodifiable)
    type            pow;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
    field           <inpField>;
    n               4;

    // Optional entries (runtime modifiable)
    checkDimensions false;
    scale           1.0;
    offset          0.0;

    // Optional (inherited) entries
    result          <fieldResult>;
    region          region0;
    enabled         true;
    pow             true;
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
| type | Type name: pow | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| n | Power exponent | scalar | yes |  |
| checkDimensions | Flag to check dimensions of the operand field | bool | no | true |
| scale | Scaling factor \- `s` above | scalar | no | 1\.0 |
| offset | Offset factor \- `t` above | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* [functionObject.H](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "pow(<inpField>)" -scale 1.0 -offset 0.0

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [pow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/pow)

API:

* [Foam::functionObjects::pow](https://api.openfoam.com/2606/Foam_functionObjects_pow.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
