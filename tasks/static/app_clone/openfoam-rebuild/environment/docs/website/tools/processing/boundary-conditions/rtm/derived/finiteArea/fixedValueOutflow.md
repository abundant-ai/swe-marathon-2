<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/fixedValueOutflow -->

# fixedValueOutflow

## Description

The `fixedValueOutflow` is a boundary condition that provides
a fixed value outflow condition for finite\-area calculations.

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
    type            fixedValueOutflow;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedValueOutflow` | word | yes | \- |

The inherited entries are elaborated in:

* faPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [fixedValueOutflow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/fixedValueOutflow)

API:

* [Foam::fixedValueOutflowFaPatchField](https://api.openfoam.com/2606/Foam_fixedValueOutflowFaPatchField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
