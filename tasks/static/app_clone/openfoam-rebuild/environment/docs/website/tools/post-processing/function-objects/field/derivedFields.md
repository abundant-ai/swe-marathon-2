<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/derivedFields -->

# derivedFields

## Description

The `derivedFields` function object computes computes two predefined
derived fields, i.e. `rhoU`, and `pTotal`, where the defined fields are
hard\-coded as follows:

rhoUrhoUrhoU
: ρu\\rho \\u ρu

pTotalpTotalpTotal
: p\+0\.5ρ∣u∣2p \+ 0\.5 \\rho \\mag{\\u}^2p\+0\.5ρ∣u∣2

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `derivedFields` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
derivedFields1
{
    // Mandatory entries (unmodifiable)
    type            derivedFields;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    derived         (rhoU pTotal);

    // Optional entries (runtime modifiable)
    rhoRef          1.0;

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
| type | Type name: derivedFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| derived | Names of operand fields (rhoU\|pTotal) | word | yes | \- |
| rhoRef | Reference density for incompressible flows | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [injectorPipe](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/gasMixing/injectorPipe)
* [squareBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/squareBend)

Source code:

* [derivedFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/derivedFields)

API:

* [Foam::functionObjects::derivedFields](https://api.openfoam.com/2606/Foam_functionObjects_derivedFields.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
