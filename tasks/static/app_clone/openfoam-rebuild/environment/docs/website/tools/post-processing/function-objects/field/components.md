<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/components -->

# components

## Description

The `components` function object extracts the components of a field and outputs
the result into new fields, where the fields possess the same sizes and
dimensions.

More than one field input per function object is not allowed. Therefore, for
each given field, a separate `components` function object should be created.

Depending on the base type of the input field, the number of output fields
and output suffixes are as follows (the base type cannot be `scalar` since
scalars have no components):

```
Base type       | Number of components | Suffixes
vector          | 3                    | (x y z)
sphericalTensor | 3                    | (x y z)
symmTensor      | 6                    | (xx xy xz yy yz zz)
tensor          | 9                    | (xx xy xz yx yy yz zx zy zz)

```

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}<Type>Field` (`Type` !\= Scalar) | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `{vol,surface}ScalarField` for each component | `$FOAM_CASE/<time>/<outField><suffix>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `components` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
components1
{
    // Mandatory entries (unmodifiable)
    type            components;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entry (runtime modifiable)
    field           <field>;

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
| type | Type name: components | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| field | Name of the operand field | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Minimal example by using the `postProcess` utility:

```
postProcess -func "components(<field>)"

```

### Notes on entries

The `components` function object is not executed for fields whose base type is
`scalar`, e.g. `volScalarField`, since `scalar` has a single component which
is itself.

The `result` entry is intentionally omitted by the `components` function object,
therefore the default names for the output fields (i.e. component suffixes)
cannot be overridden.

## Stored properties

### Fields

The `components` function object is stored on the mesh database,
using the default name:

```
<field><component>

```

For instance, for a field named `U.air`, resulting the following fields:

```
U.airx U.airy U.airz

```

The default names **cannot** be overridden by using the `result` entry.

## Further information

Tutorial:

* [bubbleColumnIATE](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/twoPhaseEulerFoam/laminar/bubbleColumnIATE)
* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [components](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/components)

API:

* [Foam::functionObjects::components](https://api.openfoam.com/2606/Foam_functionObjects_components.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
