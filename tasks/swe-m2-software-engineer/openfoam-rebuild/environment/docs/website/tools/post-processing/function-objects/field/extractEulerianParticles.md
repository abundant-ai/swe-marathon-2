<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/extractEulerianParticles -->

# extractEulerianParticles

## Description

The `extractEulerianParticles` function object generates
particle size information from Eulerian calculations, e.g. `VoF`.
It derives spherical particles by interrogating the Eulerian phase
fraction field.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| input | \- | \- |
| output file | \- | \- |
| output field 1 | scalarField | $OUTPUT/d |
| output field 2 | scalarField | $OUTPUT/soi |
| output field 3 | labelField | $OUTPUT/tag |
| output field 4 | vectorField | $OUTPUT/U |

where `$OUTPUT=$FOAM_CASE/<time>/lagrangian/eulerianParticleCloud`.

## Usage

Example of the `extractEulerianParticles` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
extractEulerianParticles1
{
    // Mandatory entries (unmodifiable)
    type            extractEulerianParticles;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    faceZone        f0;
    alpha           alpha.water;

    // Optional entries (runtime modifiable)
    alphaThreshold  0.1;
    nLocations      0;
    U               U;
    rho             rho;
    phi             phi;
    minDiameter     1e-30;
    maxDiameter     1e30;

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
| type | Type name: extractEulerianParticles | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| faceZone | Name of faceZone used as collection surface | word | yes | \- |
| alpha | Name of phase indicator field | word | yes | \- |
| alphaThreshold | Threshold for alpha field | scalar | no | 0\.1 |
| nLocations | Number of injection bins to generate | label | no | 0 |
| U | Name of velocity field | word | no | U |
| rho | Name of density field | word | no | rho |
| phi | Name of flux field | word | no | phi |
| minDiameter | Minimum diameter | scalar | no | SMALL |
| maxDiameter | Maximum diameter | scalar | no | GREAT |

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

The `faceZone` defines the particle collection surface, at which the phase
fraction field, `alpha` is interpolated to identify the particle bounds.

Each isolated Eulerian region is converted into the equivalent spherical
particle by default. Alternatively, the `nLocations` entry can be used to
agglomerate the face zone to define a set of collection faces across which
particle information is gathered. This can be useful to the derive particle
spatial distribution.
faces into a set of collection zones, for which

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `nCollectedParticles`: number of particles collected
* `collectedVolume`: volume of collected particles
* `nDiscardedParticles`: number of discarded particles
* `discardedVolume`: volume of discarded particles

## Sample output

## Further information

Tutorial:

* [eulerianInjection](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/vofToLagrangian/eulerianInjection)

Source code:

* [extractEulerianParticles](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/extractEulerianParticles/extractEulerianParticles)

API:

* [Foam::functionObjects::extractEulerianParticles](https://api.openfoam.com/2606/Foam_functionObjects_extractEulerianParticles.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
