<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/CourantNo -->

# CourantNo

## Description

The `CourantNo` function object computes the field of Courant number, i.e. `Co`,
for time\-variant simulations.

Co\=Δt τ \\text{Co} \= \\Delta\_t \\, \\tauCo\=Δt​τ
where Δt\\Delta\_tΔt​ is the time\-step size, and τ\\tauτ is a characteristic
time scale based on the local cell flow scales:

τ\=12V∑faces∣ϕi∣ \\tau \= \\frac{1}{2 V} \\sum\_{faces} \\left\| \\phi\_i \\right\|τ\=2V1​faces∑​∣ϕi​∣
Here, VVV is the cell volume, ϕ\\phiϕ the face volumetric flux,
and ∑faces\\sum\_{faces}∑faces​ summation is over all cell faces.

The Courant number provides

* a measure of the rate at which information is
transported under the influence of a flux field,
* a limiting factor for the performance of numerical schemes.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | volScalarField | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `CourantNo` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
Co1
{
    // Mandatory entries (unmodifiable)
    type            CourantNo;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    rho             rho;

    // Optional (inherited) entries
    field           <phi>;
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
| type | Type name: CourantNo | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| rho | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Example by using the `postProcess` utility:

```
postProcess -func CourantNo

```

## Stored properties

### Fields

The Courant number is stored on the mesh database, using the default name

```
Co

```

If the `field` entry is set to a value other than `phi`, the default name
becomes

```
Co(<field>)

```

This name can be overridden by using the `result` entry.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [CourantNo](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/CourantNo)

API:

* [Foam::functionObjects::CourantNo](https://api.openfoam.com/2606/Foam_functionObjects_CourantNo.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
