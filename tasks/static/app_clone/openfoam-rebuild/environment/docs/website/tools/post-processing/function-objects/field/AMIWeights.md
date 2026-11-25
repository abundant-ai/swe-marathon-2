<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/AMIWeights -->

# AMIWeights

## Description

The `AMIWeights` function object computes the min/max/average weights of
arbitrary mesh interface (AMI) patches, and optionally reports into a text file
or writes VTK surfaces of the sum of the weights and mask fields for arbitrarily
coupled mesh interface (ACMI) patches.

The motivation for the `AMIWeights` is to monitor the AMI interpolation weights
as cases that employ cyclic AMI patches are sensitive to the quality of these
weights, e.g. zero AMI interpolation weights likely lead to a simulation crash.

Output statistics per AMI include:

* patch names
* whether the patch is parallel\-distributed
* minimum and maximum sum of weights (should be 1 for a perfect match)
* minimum and maximum interpolation stencil sizes

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$POST/<file>` |
| output field | vtp | `$POST/<AMINames>_{src,tgt}.vtp` |

where `$POST=$FOAM_CASE/postProcessing/<FO>/<time>`.

## Usage

Example of the `AMIWeights` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
AMIWeights1
{
    // Mandatory entries (unmodifiable)
    type            AMIWeights;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    writeFields     false;

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
| type | Type name: AMIWeights | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| writeFields | Write weights as VTK fields | bool | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Example by using the `postProcess` utility:

```
postProcess -func AMIWeights

```

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<patch-name>:src` : source patch name
* `<patch-name>:tgt` : target patch name
* `<patch-name>:src:min(weight)` : source patch minimum weight
* `<patch-name>:src:max(weight)` : source patch maximum weight
* `<patch-name>:src:ave(weight)` : source patch average weight
* `<patch-name>:src:min(address)` : source patch minimum stencil size
* `<patch-name>:src:max(address)` : source patch maximum stencil size
* `<patch-name>:src:ave(address)` : source patch average stencil size
* `<patch-name>:tgt:min(weight)` : target patch minimum weight
* `<patch-name>:tgt:max(weight)` : target patch maximum weight
* `<patch-name>:tgt:ave(weight)` : target patch average weight
* `<patch-name>:tgt:min(address)` : target patch minimum stencil size
* `<patch-name>:tgt:max(address)` : target patch maximum stencil size
* `<patch-name>:tgt:ave(address)` : target patch average stencil size

## Further information

Tutorial:

* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)

Source code:

* [AMIWeights](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/AMIWeights)

API:

* [Foam::functionObjects::AMIWeights](https://api.openfoam.com/2606/Foam_functionObjects_AMIWeights.html)

**History:** Introduced in version [v1812](https://www.openfoam.com/news/main-news/openfoam-v1812)
