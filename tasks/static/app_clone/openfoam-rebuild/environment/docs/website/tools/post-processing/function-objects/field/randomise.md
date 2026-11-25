<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/randomise -->

# randomise

## Description

The `randomise` function object
adds a random component to an input field,
with a specified perturbation magnitude.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `randomise` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
randomise1
{
    // Mandatory entries (unmodifiable)
    type            randomise;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    magPerturbation 0.1;

    // Mandatory (inherited) entries (runtime modifiable)
    field           <inpField>;

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
| type | Type name: randomise | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| magPerturbation | The magnitude of the perturbation | scalar | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func "randomise(<field>)"

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)
* [splashPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/splashPanel)

Source code:

* [randomise](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/randomise)

API:

* [Foam::functionObjects::randomise](https://api.openfoam.com/2606/Foam_functionObjects_randomise.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
