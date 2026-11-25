<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/fixedMean -->

# fixedMean

## Description

The `fixedMean` is a general boundary condition to extrapolate a field to
the patch using the near\-cell values and adjusts the distribution to match the
specified, optionally time\-varying, mean value.

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
    type            fixedMean;
    meanValue       <Function1<Type>>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedMean` | word | yes | \- |
| `meanValue` | Mean value that the field is adjusted to maintain | Function1\<Type\> | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

## Further information

Tutorial:

* [helmholtzResonance](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance)
* [wallMountedHump](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/LES/wallMountedHump)

Source code:

* [fixedMean](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fixedMean)

API:

* [Foam::fixedMeanFvPatchField](https://api.openfoam.com/2606/Foam_fixedMeanFvPatchField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
