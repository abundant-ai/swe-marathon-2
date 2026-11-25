<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/norm -->

# norm

## Overview

The `norm` function object normalises an input field with
a chosen norm, and writes a new normalised field.

## Usage

Example of function object specification:

```
norm1
{
    // Mandatory entries
    type            norm;
    libs            (fieldFunctionObjects);
    field           <word>;
    norm            <word>;

    // Conditional entries

        // When norm = Lp
        p               <scalar>;

        // When norm = composite
        divisor         <Function1<scalar>>;

        // When norm = divisorField
        divisorField    <word>;

    // Inherited entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: norm | word | yes | \- |
| `libs` | Library name: fieldFunctionObjects | word | yes | \- |
| `field` | Name of the operand field | word | yes | \- |
| `norm` | Name of normalisation operation | word | yes | \- |
| `p` | Norm exponent for the p\-norm | scalar | conditional | \- |
| `divisor` | Norm divisor for the composite norm | Function1\<scalar\> | conditional | \- |
| `divisorField` | Divisor scalar field for the field norm | word | conditional | \- |

Options for the `norm` entry:

| Property | Description | Expression |
| --- | --- | --- |
| `L1` | L1/Taxicab norm | y\=xΣi\=1n∣xi∣\\vec{y} \= \\frac{\\vec{x}}{\\Sigma\_{i\=1}^n \\vert x\_i \\vert}y\=Σi\=1n​∣xi​∣x​ |
| `L2` | L2/Euclidean norm | y\=xx12\+...\+xn2\\vec{y} \= \\frac{\\vec{x}}{\\sqrt{x\_1^2 \+ ... \+ x\_n^2}}y\=x12​\+...\+xn2​​x​ |
| `Lp` | p norm | y\=x(Σi\=1n∣xi∣p)1/p\\vec{y} \= \\frac{\\vec{x}}{(\\Sigma\_{i\=1}^n \\vert x\_i \\vert^p)^{1/p}}y\=(Σi\=1n​∣xi​∣p)1/px​ |
| `max` | Maximum norm | y\=xmax⁡∣xi∣\\vec{y} \= \\frac{\\vec{x}}{\\max\\vert x\_i \\vert}y\=max∣xi​∣x​ |
| `composite` | Composite norm with Function1 divisor | y\=xf(t)\\vec{y} \= \\frac{\\vec{x}}{f(t)}y\=f(t)x​ |
| `divisorField` | Normalise by field | y\=xz\\vec{y} \= \\frac{\\vec{x}}{\\vec{z}}y\=zx​ |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)
* Function1

Divisor quantity is perturbed by `SMALL` value to prevent any divisions
by zero irrespective of whether the quantity is close to zero or not.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| Input | `{vol,surface,polySurface}<Type>Field` | `<case>/<time>/` |
| Output file | \- | \- |
| Output field | `{vol,surface,polySurface}<Type>Field` | `<case>/<time>/` |

where `<Type>={Scalar,Vector,SphericalTensor,SymmTensor,Tensor}`.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [norm](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/norm)

API:

* [Foam::functionObjects::norm](https://api.openfoam.com/2606/Foam_functionObjects_norm.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
