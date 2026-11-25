<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/writeFile -->

# writeFile

## Description

Base class for writing single files from the function objects.

## Usage

```
<userDefinedSubDictName1>
{
    // Mandatory and other optional entries
    ...

    // Optional (inherited) entries (runtime modifiable)
    writePrecision    8;
    writeToFile       true;
    useUserTime       true;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| writePrecision | Number of decimal points | label | no | \<system dflt\> |
| writeToFile | Flag to produce text file output | bool | no | true |
| useUserTime | Flag to use user time, e.g. degrees | bool | no | true |

## Further information

Source code:

* [writeFile](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/OpenFOAM/db/functionObjects/writeFile)

API:

* [Foam::functionObjects::writeFile](https://api.openfoam.com/2606/Foam_functionObjects_writeFile.html)
