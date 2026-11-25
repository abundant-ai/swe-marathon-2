<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldExtents -->

# fieldExtents

## Description

The `fieldExtents` function object computes the spatial minimum and maximum
extents of an input field.

The extents are derived from the bound box limits after identifying the
locations where field values exceed the user\-supplied threshold value.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `fieldExtents` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
fieldExtents1
{
    // Mandatory entries (unmodifiable)
    type            fieldExtents;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    fields              (<field1> <field2> ... <fieldN>);
    threshold           0.5;

    // Optional entries (runtime modifiable)
    internalField       true;
    referencePosition   (0 0 0);

    // Optional (inherited) entries
    writePrecision  8;
    writeToFile     true;
    useUserTime     true;
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: fieldExtents | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| threshold | Value to identify extents boundary | scalar | yes | \- |
| fields | List of operand fields | wordList | yes | \- |
| internalField | Flag to process the internal field | bool | no | true |
| referencePosition | Reference position | vector | no | (0 0 0\) |
| patches | List of patches to process | wordList | no | \<all patches\> |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

For non\-scalar fields, the magnitude of the field is employed and compared
to the value of `threshold`.

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<field-name>_internal_min` : bound box minimum for field
* `<field-name>_internal_max` : bound box maximum for field

## Further information

Tutorial:

* [rivuletPanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/rivuletPanel)

Source code:

* [fieldExtents](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldExtents)

API:

* [Foam::functionObjects::fieldExtents](https://api.openfoam.com/2606/Foam_functionObjects_fieldExtents.html)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812)
