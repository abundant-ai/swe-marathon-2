<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/wallBoundedStreamLine -->

# wallBoundedStreamLine

## Description

The `wallBoundedStreamLine` function object
generates streamline data by sampling a set of user\-specified fields along a
particle track, transported by a user\-specified velocity field, constrained
to a patch.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | `$FOAM_CASE/postProcessing/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `wallBoundedStreamLine` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
wallBoundedStreamLine1
{
    // Mandatory entries (unmodifiable)
    type            wallBoundedStreamLine;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    U               <fieldTrack>;
    fields          (<fieldTrack> <field1> ... <fieldN>);
    setFormat       vtk;
    direction       bidirectional;
    lifeTime        10000;
    cloud           particleTracks;
    seedSampleSet
    {
        type        patchSeed;
        patches     (wall);
        axis        x;
        maxPoints   20000;
    }

    // Optional entries (runtime modifiable)
    bounds          (0.2 -10 -10)(0.22 10 10);
    trackLength     1e-3;
    nSubCycle       1;
    interpolationScheme cellPoint;

    // Deprecated
    // trackForward true;

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
| type | Type name: wallBoundedStreamLine | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| U | Name of tracking velocity field | word | yes | \- |
| fields | Names of operand fields to sample | wordList | yes | \- |
| setFormat | Type of output data | word | yes | \- |
| direction | Direction to track | vector | yes | \- |
| lifetime | Maximum number of particle tracking steps | label | yes | \- |
| cloud | Name of cloud | word | yes | \- |
| seedSampleSet | Name of seeding method (see below) | word | yes | \- |
| bounds | Bounding box to trim tracks | vector | no | invertedBox |
| trackLength | Tracking segment length | scalar | no | VGREAT |
| nSubCycle | Number of tracking steps per cell | label | no | 1 |
| interpolationScheme | Interp. scheme for sample | word | no | cellPoint |

Options for the `seedSampleSet` entry:

```
uniform   | uniform particle seeding
cloud     | cloud of points
patchSeed | seeding via patch faces
triSurfaceMeshPointSet | points according to a tri-surface mesh

```

Options for the `setFormat` entry:

```
csv
ensight
gnuplot
jplot
nastran
raw
vtk
xmgr

```

Options for the `direction` entry:

```
bidirectional
forward
backward

```

The inherited entries are elaborated in:

* [functionObject](../index.md)

Usage by the `postProcess` utility is not available.

### Notes on entries

* When specifying the track resolution, the `trackLength` or `nSubCycle`
option should be used.

## Further information

Tutorial:

* [motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/motorBike)
* [motorBike\_leakDetection](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/snappyHexMesh/motorBike_leakDetection)

Source code:

* [wallBoundedStreamLine](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/wallBoundedStreamLine)

API:

* [Foam::functionObjects::wallBoundedStreamLine](https://api.openfoam.com/2606/Foam_functionObjects_wallBoundedStreamLine.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
