<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/exprField -->

# exprField

The `exprField` function object creates or modifies a field based on an
[expression](../../../../fundamentals/input-types/expression-syntax.md).

## Usage

The `exprField` function object is specified using:

```
exprField1
{
    type            exprField;
    libs            (fieldFunctionObjects);
    ...
    field           <field-name>;

    expression      <expr>; // new and modify actions only

    // Optional entries
    action          <action-type>;
    readFields      <bool>;

    fieldMask       <mask-expr>; // modify action only

    autowrite       <bool>; // default: false;
    store           <bool>; // default: true

    dimensions      <dimensions>;
}

```

Actions

* `none`: no\-op
* `new`: create a new field \- **default**
* `modify`: modify an existing field

## Examples

Create a new `pTotal` field based on an expressions for

pt\=p\+12ρ∣u∣2p\_t \= p \+ \\frac{1}{2} \\rho \| \\u \|^2pt​\=p\+21​ρ∣u∣2

```
exprField1
{
    type            exprField;
    libs            (fieldFunctionObjects);
    field           pTotal;
    expression      "p + 0.5*(rho*magSqr(U))";
    dimensions      [ Pa ];
}

```

Modify the existing `pTotal` field by setting the static pressure using the `p`
field in the region defined by

∣x∣\<0\.05\|\\vec{x}\| \< 0\.05∣x∣\<0\.05
and

xy\>0x\_y \> 0xy​\>0

```
exprField
{
    type            exprField;
    libs            (fieldFunctionObjects);
    field           pTotal;
    action          modify;

    // Static pressure only in these regions
    fieldMask       "(mag(pos()) < 0.05) && (pos().y() > 0)";
    expression      "p";
}

```

## Further information

Source code:

* [expressions](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/expressions)

API:

* [Foam::functionObjects::fvExpressionField](https://api.openfoam.com/2606/Foam_functionObjects_fvExpressionField.html)

Related:

* [expressions](../../../../fundamentals/input-types/expression-syntax.md)
