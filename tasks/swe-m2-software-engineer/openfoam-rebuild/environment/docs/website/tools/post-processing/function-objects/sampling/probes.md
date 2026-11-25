<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/probes -->

# probes

## Overview

The `probes` function object samples field values at point locations and writes
the result to file using the chosen output file format.

## Usage

Example of function object specification:

```
probes1
{
    // Mandatory entries
    type                probes;
    libs                (sampling);
    probeLocations      (<points>);
    fields              (<wordRes>);

    // Optional entries
    fixedLocations      <bool>;
    includeOutOfBounds  <bool>;
    verbose             <bool>;
    sampleOnExecute     <bool>;
    interpolationScheme <scheme-type>;

    // Inherited entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: probes | word | yes | \- |
| `libs` | Library name: sampling | word | yes | \- |
| `probeLocations` | List of probe locations | vectorList | yes | \- |
| `fields` | Names of fields to be sampled | wordRes | yes | \- |
| `fixedLocations` | Do not recalculate cells if mesh moves | bool | no | true |
| `includeOutOfBounds` | Include out\-of\-bounds locations | bool | no | true |
| `verbose` | Increase the level of verbosity to log | bool | no | false |
| `sampleOnExecute` | Sample on execution and store results | bool | no | false |
| `interpolationScheme` | Interpolation scheme to use | word | no | cell |

Options for the `interpolationScheme` entry:

| Property | Description |
| --- | --- |
| `cell` | Uses the cell value for any location within the cell. |
| `cellPatchConstrained` | Uses the cell value for any point in the cell apart from a boundary face where it uses the boundary value directly. |
| `cellPoint` | Given cell centre values and point (vertex) values decompose into tetrahedra and linear interpolate within them. |
| `cellPointFace` | Given face centre values and point (vertex) values decompose into tetrahedra and linear interpolate within them. |
| `cellPointWallModified` | Same as `interpolationCellPoint`, but if interpolating a wall face, uses cell centre value instead. |
| `pointMVC` | Given cell centre values interpolates to vertices and uses these to do a Mean Value Coordinates interpolation. |

The inherited entries are elaborated in:

* [functionObject](../index.md)

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| Input | \- | \- |
| Output file | dat | `<case>/postProcessing/<function object>/<time>/` |
| Output field | \- | \- |

## Stored properties

### Reduced data

The following data are stored by the function object for the set of sample
values, and can be used by other function objects:

* `average(<field-name>)` : average set value
* `min(<field-name>)` : minimum set value
* `max(<field-name>)` : maximum set value
* `size(<field-name>)` : size of set

## Further information

Tutorial:

* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunction)

Source code:

* [probes](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/probes)

API:

* [Foam::probes](https://api.openfoam.com/2606/Foam_probes.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
