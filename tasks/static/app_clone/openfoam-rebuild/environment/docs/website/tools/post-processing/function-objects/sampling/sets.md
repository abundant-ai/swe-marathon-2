<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/sets -->

# Points

The `sets` function object samples field values at point locations and writes
the result to file using the chosen output file format.

## Usage

Basic operation of the `sets` function object comprises:

```
sets1
{
    type            sets;
    libs            ("libsampling.so");

    setFormat       <format-type>;

    fields          (<fields>);

    interpolationScheme <scheme-type>;

    sets
    {
        mySet1
        {
            // set definition for 'mySet1'
            type            <set-type>;
            axis            <axis>;
            ...
        }
        mySet2
        {
            // set definition for 'mySet2'
            type            <set-type>;
            axis            <axis>;
            ...
        }
        ...
        mySetN
        {
            // set definition for 'mySetN'
            type            <set-type>;
            axis            <axis>;
            ...
        }
    }
}

```

Fields to be sampled are listed in the `fields` entry, e.g.

```
fields          (U p T);

```

Sets to be returned are listed in the `sets` sub\-dictionary, each in dictionary
format with a user\-supplied name, e.g. `mySet1`, `mySet2`, and `mySetN` above.

The `<set-type>` value can be set to:

* `array`: array of uniformly distributed points in a 3\-D box
* `cellCentre`: points defined at cell centres in a 3\-D box
* `circle`: uniformly distributed points on a circular path
* `face`: face intersection points on line between start and end points
* `midPoint`: mid points of face intersection points on line between start and
end points
* `midPointAndFace`: combination of `midPoint` and `face` methods
* `patchCloud`: same as `cloud`, but points constrained to nearest patch faces
* `patchEdge`: points intersecting a patches and external surfaces
* `patchSeed`: points on a patch
* `polyLine`: points on the knots of a line defined as a list of points
* `triSurfaceMeshPointSet`: all points from a `triSurfaceMesh`
* `uniform`: uniformly distributed points on line between start and end points

The `<axis>` value describes how the point co\-ordinates are written. Options
include:

* `x`, `y`, or `z`: single Cartesian co\-ordinate only
* `xyz`: Cartesian x, y, z
* `distance`:
	+ for lines: the distance from the start of the line
	+ for points: the distance from the first point

* [cloud](sets/cloud.md)
* [shortestPath](sets/shortestPath.md)

## Sample output

This information is also written in the user\-specified output format to file
in the directory:

```
$FOAM_CASE/postProcessing/<function object>/<time>

```

## Stored properties

### Reduced data

The following data are stored by the function object for the set of sample
values, and can be used by other function objects:

* `average(<field-name>)` : average set value
* `min(<field-name>)` : minimum set value
* `max(<field-name>)` : maximum set value
* `size(<field-name>)` : size of set

## Further information

Related:

* [Surface sampling](surfaces/index.md)

Source code:

* [sampledSets](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/sampledSet/sampledSets)

API:

* [Foam::sampledSets](https://api.openfoam.com/2606/Foam_sampledSets.html)

Example usage:

* buoyantSimpleFoam `buoyantCavity` tutorial:
[buoyantCavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/buoyantSimpleFoam/buoyantCavity)
