<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldValue -->

# fieldValue

## Description

The `fieldValue` class is an intermediate class for
handling field value\-based function objects.

The class is not an executable function object itself, but a provider for
common entries to its derived function objects.

## Usage

The optional\-inherited entries provided by `fieldValue` to the derived
function objects are as follows:

```
<userDefinedSubDictName1>
{
    // Mandatory and other optional entries
    ...

    // Mandatory (inherited) entries (runtime modifiable)
    fields            (<field1> <field2> ... <fieldN>);

    // Optional (inherited) entries (runtime modifiable)
    writeFields       false;
    scaleFactor       1.0;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: AMIWeights | word | yes | \- |
| fields | Names of operand fields | wordList | yes | \- |
| writeFields | Flag to output field values | bool | no | false |
| scaleFactor | Scaling factor | scalar | no | 1\.0 |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

## Further information

Source code:

* [fieldValue](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldValues/fieldValue)

API:

* [Foam::functionObjects::fieldValue](https://api.openfoam.com/2606/Foam_functionObjects_fieldValue.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
