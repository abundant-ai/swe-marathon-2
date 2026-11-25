<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/regionFiniteArea/thermalShell -->

# thermalShell

## Description

The `compressible::thermalShell` is a boundary condition that provides
a coupled temperature condition between a primary region (3D mesh)
and a thermal shell model (2D mesh).

The primary region boundary creates the finite area region
and evolves its energy equation.

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
    type            thermalShell;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::thermalShell` | word | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* thermalShellModel.H

## Further information

Tutorial:

* [hotRoomWithThermalShell](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantPimpleFoam/hotRoomWithThermalShell)

Source code:

* [thermalShell](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/regionFaModels/derivedFvPatchFields/thermalShell)

API:

* [Foam::compressible::thermalShellFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_thermalShellFvPatchScalarField.html)

**History:** Introduced in version [v1906](https://www.openfoam.com/news/main-news/openfoam-v1906)
