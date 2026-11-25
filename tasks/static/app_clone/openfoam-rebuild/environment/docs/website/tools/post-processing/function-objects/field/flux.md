<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/flux -->

# flux

## Description

The `flux` function object computes
the flux of an input vector field.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `{vol,surface}VectorField` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `surfaceScalarField` | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `flux` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
flux1
{
    // Mandatory entries (unmodifiable)
    type            flux;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    rho             none;

    // Optional (inherited) entries
    field           <field>;
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
| type | Type name: flux | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| rho | Name of density field | word | no | none |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [fieldExpression](fieldExpression.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [flux](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/flux)

API:

* [Foam::functionObjects::flux](https://api.openfoam.com/2606/Foam_functionObjects_flux.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
