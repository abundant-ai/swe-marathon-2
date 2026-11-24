<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/qZeta -->

# q\-ζ

## Properties

* Incompressible only
* Two equation model

## Model equations

## Default model coefficients

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        qZeta;
}

```

## Further information

Source code:

* [Foam::incompressible::RASModels::qZeta](https://api.openfoam.com/2606/Foam_incompressible_RASModels_qZeta.html)

References:

* Standard model: *Gibson and Dafa'Alla* [20](../../../../../../../references.md#gibson_two-equation_1995)
* OpenFOAM variant: *Dafa'Alla et al.* [12](../../../../../../../references.md#dafaalla_calculation_1996)
