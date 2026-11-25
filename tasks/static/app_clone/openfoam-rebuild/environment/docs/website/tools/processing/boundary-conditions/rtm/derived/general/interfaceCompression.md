<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/interfaceCompression -->

# interfaceCompression

## Description

The `interfaceCompression` is a generic boundary condition that applies
interface\-compression to the phase\-fraction distribution at the
patch by setting the phase\-fraction to 0 if it is below 0\.5, otherwise
to 1\.

This approach is useful to avoid unphysical "bleed" of the lighter phase
along the surface in regions of high shear adjacent to the surface which
is at a shallow angle to the interface.

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
    type            interfaceCompression;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `interfaceCompression` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [interfaceCompression](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/interfaceCompression)

API:

* [Foam::interfaceCompressionFvPatchScalarField](https://api.openfoam.com/2606/Foam_interfaceCompressionFvPatchScalarField.html)

**History:** Introduced in version [v1706](https://www.openfoam.com/news/main-news/openfoam-v1706)
