<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/streamLine -->

# streamline

## Description

The `streamLine` function object
generates streamline data by sampling a set of user\-specified fields along a
particle track, transported by a user\-specified velocity field.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | `$FOAM_CASE/postProcessing/sets/<FO>/<time>/<file>` |
| output field | \- | \- |

## Usage

Example of the `streamLine` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
streamLine1
{
    // Mandatory entries (unmodifiable)
    type            streamLine;
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
        type        uniform;
        axis        x;
        start       (-0.0205 0.0001 0.00001);
        end         (-0.0205 0.0005 0.00001);
        nPoints     100;
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
| type | Type name: streamLine | word | yes | \- |
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
uniform | uniform particle seeding
cloud   | cloud of points
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

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [streamLine](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/streamLine)

API:

* [Foam::functionObjects::streamLine](https://api.openfoam.com/2606/Foam_functionObjects_streamLine.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
