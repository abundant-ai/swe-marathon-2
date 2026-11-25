<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/log -->

# log

## Description

The `log` function object computes the
natural logarithm of an input `volScalarField`.

f\=sln⁡(max⁡(f0,a))\+t f \= s \\ln(\\max(f\_0, a)) \+ tf\=sln(max(f0​,a))\+t
where:

fff
: Output `volScalarField`

f0f\_0f0​
: Input `volScalarField`

ln⁡\\lnln
: Natural logarithm operator

aaa
: Clip scalar

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

Example of the `log` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
log1
{
    // Mandatory entries (unmodifiable)
    type            log;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
    field           <inpField>;

    // Optional entries (runtime modifiable)
    clip            1e-3;
    checkDimensions false;
    scale           1.0;
    offset          0.0;

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
| type | Type name: log | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| clip | Value to clip the operand field values to prevent zero or negative input | scalar | no | SMALL |
| checkDimensions | Flag to check dimensions of the operand field | bool | no | true |
| scale | Scaling factor \- `s` above | scalar | no | 1\.0 |
| offset | Offset factor \- `t` above | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* [functionObject.H](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "log(<inpField>)" -scale 1.0 -offset 0.0

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [log](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/log)

API:

* [Foam::functionObjects::log](https://api.openfoam.com/2606/Foam_functionObjects_log.html)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
