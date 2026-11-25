<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/greyDiffusiveViewFactor -->

# greyDiffusiveViewFactor

## Description

The `greyDiffusiveViewFactor` is a boundary condition that
provides a grey\-diffuse condition for radiative heat flux, `qr`,
for use with the view factor model.

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
    type            greyDiffusiveViewFactor;
    qro             <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `greyDiffusiveViewFactor` | word | yes | \- |
| `qro` | External radiative heat flux | scalarField | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* N/A

Source code:

* [greyDiffusiveViewFactor](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/radiation/derivedFvPatchFields/greyDiffusiveViewFactor)

API:

* [Foam::radiation::greyDiffusiveViewFactorFixedValueFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_greyDiffusiveViewFactorFixedValueFvPatchScalarField.html)

**History:** Introduced in version [2\.4\.0](https://www.openfoam.com/news/main-news/openfoam-2.4.0)
