<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/fluxSummary -->

# fluxSummary

## Description

The `fluxSummary` function object computes
the volumetric\- or mass\-flux information across selections of face zones.

Statistics include:

* positive flux:

ϕ\+\=∑ϕ\>0\\phi\_{\+} \= \\sum \\phi\_{\>0}ϕ\+​\=∑ϕ\>0​

* negative flux:

ϕ−\=∑ϕ\<0\\phi\_{\-} \= \\sum \\phi\_{\<0}ϕ−​\=∑ϕ\<0​

* net flux:

ϕnet\=∑ϕ\\phi\_{\\mathrm{net}} \= \\sum \\phiϕnet​\=∑ϕ

* absolute flux:

ϕabs\=∑∣ϕ∣\\phi\_{\\mathrm{abs}} \= \\sum \|{\\phi}\|ϕabs​\=∑∣ϕ∣

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | dat | `$FOAM_CASE/postProcessing/<FO>/<time>/<faceN>` |
| output field | \- | \- |

## Usage

Example of the `fluxSummary` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
fluxSummary1
{
    // Mandatory entries (unmodifiable)
    type            fluxSummary;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    mode            cellZoneAndDirection;
    cellZoneAndDirection
    (
        (porosity (1 0 0))
    );

    // Optional entries  (runtime modifiable)
    phi             phi;
    scaleFactor     1.0;
    tolerance       0.8;

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
| type | Type name: fluxSummary | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| mode | Mode to generate faces to test | word | yes | \- |
| phi | Name of surface flux field | word | no | phi |
| scaleFactor | Factor to scale results | scalar | no | 1\.0 |
| tolerance | Tolerance for reference direction | scalar | no | 0\.8 |

Options for the `mode` entry:

```
faceZone
faceZoneAndDirection | faceZone with prescribed positive direction
cellZoneAndDirection | cellZone with prescribed positive direction
surface
surfaceAndDirection

```

The inherited entries are elaborated in:

* [functionObject](../index.md)
* [writeFile](writeFile.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

* For surface and direction, `phi=U` can be used for determining the fluxes.
* In case of `mode=cellZoneAndDirection`, faces bounding the `cellZone`
are extracted and processed.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [fluxSummary](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/fluxSummary)

API:

* [Foam::functionObjects::fluxSummary](https://api.openfoam.com/2606/Foam_functionObjects_fluxSummary.html)

**History:** Introduced in version [v1612\+](https://www.openfoam.com/news/main-news/openfoam-v1612+)
