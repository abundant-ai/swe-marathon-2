<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/reference -->

# reference

## Description

The `reference` function object
computes a field whose values are offset to a reference
value obtained by sampling the field at a user\-specified location.

The field values are calculated using:

refc\=s(fc(t)−fp\+foff) \\text{ref}\_c \= s(f\_{c}(t) \- f\_p \+ f\_{off})refc​\=s(fc​(t)−fp​\+foff​)
where:

refc\\text{ref}\_crefc​
: Field values at cell

sss
: Optional scale factor (default \= 1\)

fc(t)f\_{c}(t)fc​(t)
: Current field values at cell at this time

fpf\_pfp​
: Field value at position

fofff\_{off}foff​
: Offset field value (default \= 0\)

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `{vol,surface}<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `reference` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
reference1
{
    // Mandatory entries (unmodifiable)
    type            reference;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries (runtime modifiable)
    field           <inpField>;

    // Optional entries (runtime modifiable)
    position    (0 0 0);
    scale       1.0;
    offset      0.0;
    interpolationScheme    cell;

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
| type | Type name: reference | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |
| position | Position to sample | vector | no | \<not used\> |
| scale | Scale value | scalar | no | 1\.0 |
| offset | Offset value | scalar | no | 0\.0 |
| interpolationScheme | Sampling scheme | word | no | cell |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "reference(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [reference](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/reference)

API:

* [Foam::functionObjects::reference](https://api.openfoam.com/2606/Foam_functionObjects_reference.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
