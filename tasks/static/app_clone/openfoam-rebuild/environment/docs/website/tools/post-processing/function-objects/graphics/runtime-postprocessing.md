<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/graphics/runtime-postprocessing -->

# Run\-time post\-processing

The `runTimePostProcessing` function object generates images by assembling
and compositing scene objects, typically produced via function objects.

* Generate a static image, or a sequence of images
* Render points, lines and surfaces
* Optional scalar bar
* Perspective and parallel camera modes
* Various colour maps

This object has a dependency on the [VTK](http://www.vtk.org) libraries

## Usage

The `runTimePostProcessing` function object is specified using multiple
sub\-dictionaries that describe the desired output, camera and scene object
settings:

```
runTimePostPro1
{
    type            runTimePostProcessing;
    libs            ("librunTimePostProcessing.so");

    // Image properties
    output
    {
        ...
    }

    // Visualisation properties
    camera
    {
        ...
    }

    // Default colours
    colours
    {
        ...
    }

    // Scene objects

    lines
    {
        ...
    }

    surfaces
    {
        ...
    }

    text
    {
        ...
    }
}

```

### output

The `output` sub\-dictionary describes properties of the output `png` file

```
output
{
    name            image;
    width           2000;
    height          1200;
}

```

### camera

Basic operation of a static `camera` comprises:

```
camera
{
    // Parallel projection flag
    parallelProjection  no;

    // Camera geometry
    focalPoint      (1.2 1.1 0.2);
    up              (0 0 1);
    position        (3.6 5.1 -1.3);

    // Optional properties

    // Restrict the view to a clip box
    clipBox         (-0.2 -0.2 0)(1.65 0.2 1.25);
}

```

Optionally, the camera can move. Each of the camera geometry controls is a
Foam::Function1 type, and can be set to vary as a function of scene time using
e.g. tabulated, polynomial, sinusoidal profiles etc. The scene time is
defined as a linear function between zero and one.

An example using tabulated entries is given by:

```
camera
{
    // Parallel projection flag
    parallelProjection  no;

    // Camera geometry
    focalPoint      (1.2 1.1 0.2);
    up              (0 0 1);
    position        (3.6 5.1 -1.3);

    // Optional properties

    // If camera is moving, optionally provide start and end times
    // Note: specified in scene time in range 0-1
    startPosition    0.2;
    endPosition      0.75;

    // Total number of frames to generate
    nFrameTotal      20;
}

```

### colours

The `colours` sub\-dictionary defines the set of default colours to employ
for the background, and scene objects when the `colourBy` entry is set to
`colour`.

```
colours
{
    background      (1 1 1);

    text            (0 0 0);
    edge            (1 0 0);
    surface         (0.5 0.5 0.5);
    line            (1 0 0);

    // Optional

    // Set a second background colour to produce a graded background
    background2     (0 0 1);
}

```

### Scene objects

Scene objects provide the main focus of the image, e.g. lines, surfaces and
text. All objects have a `visible` property to optionally hide the object.

### lines

The `lines` sub\-dictionary describes line\-based data, e.g. the output from
stream lines. Valid line types include:

* `functionObjectLine`: line based data produced by a function object

```
lines
{
    streamline
    {
        type            functionObjectLine;
        functionObject  streamLines;
        representation  tube;
        visible         yes;
        tubeRadius      0.01;
        colourBy        field;
        field           U;
        range           (0 20);
        opacity         1;
    }
}

```

## Sample output

* Portable Network Graphic (PNG) images

## Further information

Related:

* [Point sampling](../sampling/sets.md)
* [Surface sampling](../sampling/surfaces.md)

API:

* [Foam::functionObjects::runTimePostPro::runTimePostProcessing](https://api.openfoam.com/2606/Foam_functionObjects_runTimePostPro_runTimePostProcessing.html)

Example usage:

* [pisoFoam](../../../processing/solvers/rtm/incompressible/pisoFoam.md) `motorBike` tutorial:
[motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/LES/motorBike/motorBike)

**History:** Introduced in version [v3\.0\+](https://www.openfoam.com/news/main-news/openfoam-v3.0+)
