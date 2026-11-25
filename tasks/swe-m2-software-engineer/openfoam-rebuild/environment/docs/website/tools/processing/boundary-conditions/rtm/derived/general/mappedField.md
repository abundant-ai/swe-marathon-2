<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/mappedField -->

# mappedField

## Description

The `mappedField` is a generic boundary condition that provides a
self\-contained version of the `mapped` condition. It does not use information
on the patch; instead it holds the data locally.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            mappedPatch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type                    mappedField;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `mappedField` | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::mappedPatchBase](https://api.openfoam.com/2606/Foam_mappedPatchBase.html)
* [Foam::mappedPatchFieldBase](https://api.openfoam.com/2606/Foam_mappedPatchFieldBase.html)
* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

* Since this condition can be applied on a per\-field and per\-patch basis,
it is possible to duplicate the mapping information. If possible, employ
the `mapped` condition in preference to avoid this situation, and only
employ this condition if it is not possible to change the underlying
geometric (poly) patch type to `mapped`.

## Further information

Tutorial:

* [flameSpreadWaterSuppressionPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/flameSpreadWaterSuppressionPanel)
* [oppositeBurningPanels](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/oppositeBurningPanels)

Source code:

* [mappedField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/mappedField)

API:

* [Foam::mappedFieldFvPatchField](https://api.openfoam.com/2606/Foam_mappedFieldFvPatchField.html)

**History:** Introduced in version [2\.1\.0](https://www.openfoam.com/news/main-news/openfoam-2.1.0)
