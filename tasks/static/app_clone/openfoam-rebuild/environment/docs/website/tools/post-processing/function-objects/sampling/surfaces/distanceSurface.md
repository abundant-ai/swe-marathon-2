<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/distanceSurface -->

# distanceSurface

Creates a cutting plane through a mesh.

## Usage

Basic operation of the `distanceSurface` surface comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaces
    {
        mySurface1
        {
            type            distanceSurface;
            surfaceType     triSurfaceMesh;

            // Optional
            surfaceName     mySurface.obj;
            distance        0;
            signed          true;
            topology        <topology-type>;
            absProximity    1e-5;
            maxDistance     1000;
        }
    }
}

```

The `topology-type` value can be::

* `none` : no filtering

Pre\-filter options:

* `largestRegion`: pre\-filter \- retains the region with the most cut cells
* `nearestPoints` : pre\-filter \- retains the regions where cut cells are closest to the set user\-defined points. Requires additional
input:

```
topology        nearestPoints;
nearestPoints
(
    (0 0 0)
    (1 0 0)
    (1 1 0)
);

```

Post\-filter options:

* `proximityRegions`: post filter \- uses the area\-weighted distance of each
topologically connected region to the input surface to reject regions at a distance greater than `absProximity`
* `proximityFaces`: post\-filter \- rejects resulting faces with a distance greater than `absProximity` from the input surface
* `proximity`: post\-filter \- same as `proximityFaces`

## Sample output

## Further information

Source code:

* [distanceSurface](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/surface/distanceSurface)

API:

* [Foam::distanceSurface](https://api.openfoam.com/2606/Foam_distanceSurface.html)

Example usage:

* [injectorPipe](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/gasMixing/injectorPipe)
* [squareBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBend)
