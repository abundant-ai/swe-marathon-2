<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldsExpression -->

# fieldsExpression

## Description

The `fieldsExpression` class is an intermediate class for handling field
expression function objects (e.g. `add`, `subtract` etc.) whereinto more
than one fields are input.

The class is not an executable function object itself, yet a provider for
common entries to its derived function objects.

## Usage

The optional\-inherited entries provided by `fieldsExpression` to the derived
function objects are as follows:

```
<userDefinedSubDictName1>
{
    // Mandatory and other optional entries
    ...

    // Optional (inherited) entries (runtime modifiable)
    fields            (<field1> <field2> ... <fieldN>);
    result            <fieldResult>;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| fields | Names of the operand fields | wordList | yes | \- |
| result | Names of the output fields | wordList | no | \<FO\>(\<f1\>,...) |

## Further information

Source code:

* [fieldsExpression](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldsExpression)

API:

* [Foam::functionObjects::fieldsExpression](https://api.openfoam.com/2606/Foam_functionObjects_fieldsExpression.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
