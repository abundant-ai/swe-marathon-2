<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/wallShearStress -->

# wallShearStress

## Description

The `wallShearStress` function object computes the wall\-shear stress at selected
wall patches.

τ\=R⋅n \\vec \\tau \= \\vec R \\cdot \\vec nτ\=R⋅n
where:

τ\\vec \\tauτ
: Wall shear stress vector \[m2/s2]

R\\vec RR
: Shear\-stress symmetric tensor (retrieved from turbulence model)

n\\vec nn
: Patch normal vector (into the domain)

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<field>` |
| output field | `volVectorField` (only boundaryField) | `$FOAM_CASE/<time>/<outField>` |

## Usage

Example of the `wallShearStress` function object by using `functions`
sub\-dictionary in `system/controlDict` file:

```
wallShearStress1
{
    // Mandatory entries (unmodifiable)
    type            wallShearStress;
    libs            (fieldFunctionObjects);

    // Optional entries (runtime modifiable)
    patches         (<patch1> ... <patchN>); // (wall1 "(wall2|wall3)");

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

```

}

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: wallShearStress | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| patches | Names of operand patches | wordList | no | all wall patches |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Example by using the `postProcess` utility:

```
<solver> -postProcess -func wallShearStress

```

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [wallShearStress](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/wallShearStress)

API:

* [Foam::functionObjects::wallShearStress](https://api.openfoam.com/2606/Foam_functionObjects_wallShearStress.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
