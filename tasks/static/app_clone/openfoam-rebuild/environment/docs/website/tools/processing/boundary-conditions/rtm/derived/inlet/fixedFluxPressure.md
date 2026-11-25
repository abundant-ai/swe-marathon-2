<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/fixedFluxPressure -->

# fixedFluxPressure

## Description

The `fixedFluxPressure` is a pressure boundary condition to
set the pressure gradient to the provided value such that the flux on
the boundary is that specified by the velocity boundary condition.
This condition ensures the correct flux at fixed\-flux boundaries by
compensating for the body forces (gravity in particular) with the
pressure gradient.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            fixedFluxPressure;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedFluxPressure` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedGradientFvPatchField](https://api.openfoam.com/2606/Foam_fixedGradientFvPatchField.html)
* [Foam::updateableSnGrad](https://api.openfoam.com/2606/Foam_updateableSnGrad.html)

## Further information

Tutorial:

* [hotRoom](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantBoussinesqPimpleFoam/hotRoom)

Source code:

* [fixedFluxPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedFluxPressure)

API:

* [Foam::fixedFluxPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_fixedFluxPressureFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
