<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/utilities/writeDictionary -->

# writeDictionary

The `writeDictionary` function object writes dictionaries on start\-up, and
if changed.

## Usage

The `writeDictionary` function object is specified using:

```
writeDictionary1
{
    type        writeDictionary;
    libs        ("libutilityFunctionObjects.so");
    dictNames   (fvSchemes fvSolution)
}

```

## Sample output

## Further information

Source code:

* [writeDictionary](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/utilities/writeDictionary)

API:

* [Foam::functionObjects::writeDictionary](https://api.openfoam.com/2606/Foam_functionObjects_writeDictionary.html)
