<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/LambVector -->

# LambVector

## Description

The `LambVector` function object computes
'Lamb vector' \[m/s2] [79](../../../../references.md#truesdell_kinematics_2018) (p. 77\) which is the
cross product of a velocity vector \[m/s] and vorticity vector \[1/s].

`LambVector` is defined as follows:

l\=ω×u\\mathbf{l} \= \\vec{\\omega} \\times \\ul\=ω×u
where ω(x,t)≡ω\\vec{\\omega}(\\mathbf{x},t) \\equiv \\vec{\\omega}ω(x,t)≡ω is the
vorticity vector,
and u(x,t)≡u\\u (\\mathbf{x}, t) \\equiv \\uu(x,t)≡u the velocity vector.

The motivation of `LambVector` function object is the literature\-reported
quantitative connection between the Lamb vector (divergence) and the spatially
localised instantaneous fluid motions, e.g. high\- and low\-momentum fluid
parcels, which possess considerable level of capacity to affect the rate of
change of momentum, and to generate forces such as drag.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `volVectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `volScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `LambVector` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
LambVector1
{
    // Mandatory entries (unmodifiable)
    type        LambVector;
    libs        (fieldFunctionObjects);

    // Optional (inherited) entries
    field           <inpField>;
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
| type | Type name: LambVector | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Usage by the `postProcess` utility is not available.

An example of the usage involving the divergence computation of the `LambVector`
can be seen below:

In `controlDict.functions`:

```
LambVector1
{
    type        LambVector;
    libs        (fieldFunctionObjects);
    field       U;
}

div1
{
    type        div;
    libs        (fieldFunctionObjects);
    field       LambVector;
}

fieldAverage1
{
    type            fieldAverage;
    libs            (fieldFunctionObjects);
    writeControl    writeTime;
    fields
    (
        LambVector
        {
            mean        on;
            prime2Mean  off;
            base        time;
        }

       div(LambVector)
       {
           mean        on;
           prime2Mean  off;
           base        time;
       }
    );
}

```

Please note that if `default divScheme` is `none`, in `fvSchemes.divSchemes`, a
numerical scheme should be chosen for related quantities, e.g. `div(LambVector)`
as follows:

```
div(LambVector)  Gauss linear;

```

## Further information

Tutorial:

* [pisoFoam](../../../processing/solvers/rtm/incompressible/pisoFoam.md)
`cavity` tutorial: [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [LambVector](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/LambVector)

API:

* [Foam::functionObjects::LambVector](https://api.openfoam.com/2606/Foam_functionObjects_LambVector.html)

Related:

* [Vorticity](vorticity.md)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906) ]
