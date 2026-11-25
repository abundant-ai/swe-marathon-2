<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldExpression -->

# fieldExpression

## Description

Intermediate class for handling field expression function objects
(e.g. `blendingFactor` etc.) whereinto a single field is input.

The class is not an executable function object itself, yet a provider for
common entries to its derived function objects.

## Usage

The optional\-inherited entries provided by `fieldExpression` to the derived
function objects are as follows:

```
<userDefinedSubDictName1>
{
    // Mandatory and other optional entries
    ...

    // Optional (inherited) entries (runtime modifiable)
    field             <field>;
    result            <fieldResult>;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| field | Name of the operand field | word | yes | \- |
| result | Name of the output field | wordList | no | \<FO\>(\<f1\>,...) |

## Further information

Source code:

* [fieldExpression](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldExpression)

API:

* [Foam::functionObjects::fieldExpression](https://api.openfoam.com/2606/Foam_functionObjects_fieldExpression.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
