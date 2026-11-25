<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fieldAverageItem -->

# fieldAverageItem

## Description

Helper class to describe what form of averaging to apply. A set will be
applied to each base field in `Foam::fieldAverage`, of the following form.

## Usage

```
<field1>
{
    mean            on;
    prime2Mean      on;
    base            time; // iteration
    window          200;  // optional averaging window
    windowName      w1;   // optional window name (default = "")
    windowType      approximate; // window type

    allowRestart    yes;  // optional, used for windowType 'exact'
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| mean | Flag to calculate average | bool | yes | \- |
| prime2Mean | Flag to calculate prime\-square average | bool | yes | \- |
| base | Type of averaging interval | word | yes | \- |
| window | Averaging window | scalar | no | \- |
| windowName | Name of the averaging window | word | no | \- |
| windowType | Type of averaging window | word | no | \- |
| allowRestart | Flag to allow restart for windowType\=exact | bool | no | \- |

Options for the `base` entry:

```
time | Averaging interval is based on time
iter | Averaging interval is based on iterations

```

Options for the `windowType` entry:

```
none  | no windowing
exact | allow additional files will be stored and written
approximate | disallow additional files will be stored and written

```

To employ the `prime2Mean` option, the `mean` option must be enabled.

## Further information

Source code:

* [fieldAverageItem](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fieldAverage/fieldAverageItem)

API:

* [Foam::functionObjects::fieldAverageItem](https://api.openfoam.com/2606/Foam_functionObjects_fieldAverageItem.html)
