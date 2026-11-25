<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/ -->

# Surfaces

The `surfaces` function object samples field values on surfaces and writes
the result to file using the chosen output file format.

## Usage

Basic operation of the `surfaces` function object comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaceFormat   <format-type>;
    formatOptions
    {
        <format-type>
        {
            <options>
        }
    }

    fields          (<fields>);

    interpolationScheme <scheme-type>;

    surfaces
    {
        mySurface1
        {
            // set definition for 'mySurface1'
            type            <surface-type>;
            ...
        }
        mySurface2
        {
            // set definition for 'mySurface2'
            type            <surface-type>;
            ...
        }
        ...
        mySurfaceN
        {
            // set definition for 'mySurfaceN'
            type            <surface-type>;
            ...
        }
    }
}

```

Surfaces to be returned are listed in the `surfaces` sub\-dictionary, each in
dictionary format with a user\-supplied name, e.g. `mySurface1`, `mySurface2`,
and `mySurfaceN` above.

## Options

The `<surface-type>` value can be set to:

* [cuttingPlane](cuttingPlane.md)
* [distanceSurface](distanceSurface.md)
* [isoSurfaceCell](isoSurfaceCell.md)
* [sampledIsoSurface](isoSurface.md)
* [sampledMeshedSurface](sampledMeshedSurface.md)

## Surface format

The surface output format is controlled using the `surfaceFormat` entry, with
additional format controls in the optional `formatOptions` sub\-dictionary.
For example, to generate EnSight surfaces in ASCII format with collated times:

```
surfaceFormat       ensight;

// Optional controls
formatOptions
{
    ensight
    {
        format          ascii;
        collateTimes    true;
    }
}

```

Available surface format options that include both geometry and data are:

* `abaqus` : Abaqus
* `ensight` : EnSight
* `nastran` : nastran
* `vtk` : VTK

Further options are available, but are limited to geometry only, e.g.

* `obj` : Lightwave OBJ
* `stl` : STL

## Sample output

This information is also written in the user\-specified output format to file
in the directory:

```
$FOAM_CASE/postProcessing/<function object>/<time>

```

## Further information

Source code:

* [sampledSurfaces](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/sampledSurface/sampledSurfaces)

API:

* [Foam::sampledSurfaces](https://api.openfoam.com/2606/Foam_sampledSurfaces.html)

Example usage:

* [pimpleFoam](../../../../processing/solvers/rtm/incompressible/pimpleFoam.md) `propeller` tutorial:
[propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
