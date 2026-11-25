<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/finiteArea/ignore -->

# ignore

## Description

The `ignore` is a boundary condition that provides
a zero gradient condition which ignores invalid edges.
This condition is a placeholder; its naming and definition are still subject to
change.

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
    type            ignore;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `ignore` | word | yes | \- |

The inherited entries are elaborated in:

* faPatchFields.H

## Further information

Tutorial:

* N/A

Source code:

* [ignore](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteArea/fields/faPatchFields/derived/ignore)

API:

* [Foam::ignoreFaPatchField](https://api.openfoam.com/2606/Foam_ignoreFaPatchField.html)

**History:** Introduced in version [v2306](https://www.openfoam.com/news/main-news/openfoam-v2306)
