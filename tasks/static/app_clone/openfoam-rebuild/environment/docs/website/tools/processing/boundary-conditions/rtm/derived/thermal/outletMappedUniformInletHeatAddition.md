<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/outletMappedUniformInletHeatAddition -->

# outletMappedUniformInletHeatAddition

## Description

The `outletMappedUniformInletHeatAddition` is a boundary condition that provides
a temperature boundary condition averages the temperature over the
"outlet" patch specified by name "outletPatchName" and applies an extra
heat source. This is set as a uniform temperature value on this patch.

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
    type            outletMappedUniformInletHeatAddition;
    outletPatch     <word>;
    Q               <scalar>;

    // Optional entries
    phi             <word>;
    TMin            <scalar>;
    TMax            <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletMappedUniformInletHeatAddition` | word | yes | \- |
| `outletPatch` | Name of the outlet patch to be mapped | word | yes | \- |
| `Q` | Heat addition \[W] | scalar | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `TMin` | Minimum temperature limit | scalar | no | 0 |
| `TMax` | Maximum temperature limit | scalar | no | 5000 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/TJunction)

Source code:

* [outletMappedUniformInletHeatAddition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/outletMappedUniformInletHeatAddition)

API:

* [Foam::outletMappedUniformInletHeatAdditionFvPatchField](https://api.openfoam.com/2606/Foam_outletMappedUniformInletHeatAdditionFvPatchField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
