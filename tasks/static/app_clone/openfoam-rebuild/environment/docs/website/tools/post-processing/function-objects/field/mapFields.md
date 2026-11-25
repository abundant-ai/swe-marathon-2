<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/mapFields -->

# mapFields

## Description

The `mapFields` function object
maps input fields from local mesh to secondary mesh at runtime.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | `vol<Type>Field` | `$FOAM_CASE/<time>/<inpField>` |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `mapFields` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
mapFields1
{
    // Mandatory entries (unmodifiable)
    type            mapFields;
    libs            (fieldFunctionObjects);

    // Mandatory (inherited) entries (runtime modifiable)
    fields          (<field1> <field2> ... <fieldN>);
    mapRegion       coarseMesh;
    mapMethod       cellVolumeWeight;
    consistent      true;

    // Optional entries (runtime modifiable)
    // patchMapMethod  direct;  // AMI-related entry
    // enabled if consistent=false
    // patchMap        (<patchSrc> <patchTgt>);
    // cuttingPatches  (<patchTgt1> <patchTgt2> ... <patchTgtN>);

    // Optional (inherited) entries
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
| type | Type name: mapFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of operand fields | wordList | yes | \- |
| mapRegion | Name of region to map to | word | yes | \- |
| mapMethod | Mapping method | word | yes | \- |
| consistent | Mapping meshes have consistent boundaries | bool | yes | \- |
| patchMapMethod | Patch mapping method for AMI cases | word | no | \- |
| patchMap | Coincident source/target patches in two cases | wordHashTable | no | \- |
| cuttingPatches | Target patches cutting the source domain | wordList | no | \- |

Options for the `mapMethod` entry:

```
direct
mapNearest
cellVolumeWeight
correctedCellVolumeWeight

```

Options for the `patchMapMethod` entry:

```
directAMI
mapNearestAMI
faceAreaWeightAMI
partialFaceAreaWeightAMI

```

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

## Further information

Tutorial:

* [cavityClipped](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/icoFoam/cavity/cavityClipped)
* [Goldschmidt](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/DPMFoam/Goldschmidt)
* [throttle3D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/cavitatingFoam/LES/throttle3D)
* [simplePipeCage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/preProcessing/PDRsetFields/simplePipeCage)

Source code:

* [mapFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/mapFields)

API:

* [Foam::functionObjects::mapFields](https://api.openfoam.com/2606/Foam_functionObjects_mapFields.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
