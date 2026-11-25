<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/patchProbes -->

# patchProbes

## Overview

The `patchProbes` function object samples patch field values at point locations
and writes the result to file using the chosen output file format.

## Usage

Example of function object specification:

```
patchProbes1
{
    // Mandatory entries
    type                patchProbes;
    libs                (sampling);

    // Conditional entries

        // Specify either 'patch' or 'patches'
        // - if both entries are present, 'patches' wins
        patch               <word>;
        patches             (<wordRes>);

    // Inherited entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: patchProbes | word | yes | \- |
| `libs` | Library name: sampling | word | yes | \- |
| `patch` | Name of operand patch | word | choice | \- |
| `patches` | Names of operand patches | wordRes | choice | \- |

The inherited entries are elaborated in:

* [probes](probes.md)

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

* [backwardFacingStep2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/backwardFacingStep2D)

Source code:

* [probes](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/probes)

API:

* [Foam::patchProbes](https://api.openfoam.com/2606/Foam_patchProbes.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
