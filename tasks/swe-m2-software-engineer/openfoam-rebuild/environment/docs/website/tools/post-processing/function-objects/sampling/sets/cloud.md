<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/sets/cloud -->

# cloud

The `cloud` set samples field values at list of point locations.

## Usage

Basic operation of the `cloud` set comprises:

```
sets1
{
    type            sets;
    libs            (sampling);

    mySet1
    {
        type            cloud;
        axis            <axis>;
        points          (<points>);
    }
}

```

Points to be sampled are listed by the `points` entry, e.g. to sample the
locations (0 0 0\), (1, 0, 0\) and (2, 0, 0\):

```
sets1
{
    type            sets;
    libs            (sampling);

    mySet1
    {
        type            cloud;
        axis            xyz; // write x, y, z co-ordinates
        points
        (
            (0 0 0)
            (1 0 0)
            (2 0 0)
        );
    }
}

```

## Further information

Related:

* [Foam::patchCloudSet](https://api.openfoam.com/2606/Foam_patchCloudSet.html)

Source code:

* [cloud](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/sampledSet/cloud)

API:

* [Foam::cloudSet](https://api.openfoam.com/2606/Foam_cloudSet.html)

Example usage:

* simpleFoam tutorials:
	+ [backwardFacingStep2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/backwardFacingStep2D)
	+ [simpleCar](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/simpleCar)
