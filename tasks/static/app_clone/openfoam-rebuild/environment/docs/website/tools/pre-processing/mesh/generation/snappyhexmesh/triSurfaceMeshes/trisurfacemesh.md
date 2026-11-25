<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/triSurfaceMeshes/trisurfacemesh -->

# triSurfaceMesh

## Usage

An example use of the `triSurfaceMesh`:

```
sphere.stl // name of the geometrical entity
{
    type    triSurfaceMesh;

    // Per region the patch name. If not provided will be <surface>_<region>.
    // Note: this name cannot be used to identity this region in any
    //       other part of this dictionary; it is only a name
    //       for the combination of surface+region (which is only used
    //       when creating patches)
    regions
    {
        secondSolid
        {
            name mySecondPatch;
        }
    }
}

```

Optional entries include:

```
// Tolerance to use for intersection tests
tolerance           1e-5;

// Scale factor to apply to the points
scale               0.001;

// Name to use to refer to this surface
name                surface1;

```

See also

* [distributedTriSurfaceMesh](distributedtrisurfacemesh.md)
