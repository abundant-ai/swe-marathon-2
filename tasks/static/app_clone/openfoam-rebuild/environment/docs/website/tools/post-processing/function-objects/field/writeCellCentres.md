<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/writeCellCentres -->

# writeCellCentres

## Description

The `writeCellCentres` function object writes the cell\-centres volVectorField
and the three component fields as `volScalarField`s.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field 1 | `volVectorField` | `$FOAM_CASE/<time>/C` |
| output field 2 | `volScalarField` | `$FOAM_CASE/<time>/{Cx,Cy,Cz}` |

## Usage

Example of the `writeCellCentres` function object by using `functions`
sub\-dictionary in `system/controlDict` file:

```
writeCellCentres1
{
    // Mandatory entries (unmodifiable)
    type            writeCellCentres;
    libs            (fieldFunctionObjects);

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
| type | Type name: writeCellCentres | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Example by using the `postProcess` utility:

```
postProcess -func writeCellCentres

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [writeCellCentres](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/writeCellCentres)

API:

* [Foam::functionObjects::writeCellCentres](https://api.openfoam.com/2606/Foam_functionObjects_writeCellCentres.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
