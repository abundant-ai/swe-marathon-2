<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/utilities/ensightWrite -->

# ensightWrite

## Overview

The `ensightWrite` function object writes OpenFOAM fields in EnSight format.

## Usage

Example of function object specification:

```
ensightWrite1
{
    // Mandatory entries
    type            ensightWrite;
    libs            (utilityFunctionObjects);
    fields          (<wordRes>);

    // Optional entries
    blockFields     (<wordRes>);
    boundary        <bool>;
    internal        <bool>;
    nodeValues      <bool>;

    format          <word>;
    width           <label>;
    directory       <fileName>;
    overwrite       <bool>;
    consecutive     <bool>;

    faceZones       (<wordRes>);
    patches         (<wordRes>);
    excludePatches  (<wordRes>);

    selection
    {
        <selection-1>
        {
            action          <action-type>;
            source          <source-type>;
            <source-entries>
        }
        <selection-2>
        {
            action          <action-type>;
            source          <source-type>;
            <source-entries>
        }
        ...
        <selection-3>
        {
            action          <action-type>;
            source          <source-type>;
            <source-entries>
        }
    }

    // Inherited entries
    ...
}

```

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `ensightWrite` | word | yes | \- |
| `libs` | Library name: fieldFunctionObjects | word | yes | \- |
| `fields` | Names of operand fields | wordRes | yes | \- |
| `blockFields` | Excluded fields from output | wordRes | no | \- |
| `boundary` | Convert boundary fields | bool | no | true |
| `internal` | Convert internal fields | bool | no | true |
| `nodeValues` | Write values at nodes | bool | no | false |
| `format` | ascii or binary format | word | no | same as simulation |
| `width` | Mask width for \\c data/XXXX | label | no | 8 |
| `directory` | The output directory name | word | no | postProcessing/NAME |
| `overwrite` | Remove existing directory | bool | no | false |
| `consecutive` | Consecutive output numbering | bool | no | false |
| `faceZones` | Names of operand face zones | wordRes | no | \- |
| `patches` | Names of operand patches | wordRes | no | \- |
| `excludePatches` | Names of excluded patches | wordRes | no | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

## Further information

Tutorial:

* [motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/motorBike)

Source code:

* [ensightWrite](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/utilities/ensightWrite)

API:

* [Foam::functionObjects::ensightWrite](https://api.openfoam.com/2606/Foam_functionObjects_ensightWrite.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
