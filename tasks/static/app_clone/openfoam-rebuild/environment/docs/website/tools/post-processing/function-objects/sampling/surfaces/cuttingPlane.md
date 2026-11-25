<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/sampling/surfaces/cuttingPlane -->

# cuttingPlane

Creates a cutting plane through a mesh using a point on the plane and plane normal.

## Usage

Basic operation of the `cuttingPlane` surface comprises:

```
surfaces1
{
    type            surfaces;
    libs            (sampling);

    surfaces
    {
        mySurface1
        {
            type        cuttingPlane;
            point       <point>;
            normal      <vector>;
        }
    }
}

```

## Sample output

## Further information

Source code:

* [cutting](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/sampling/surface/cutting)

API:

* [Foam::cuttingPlane](https://api.openfoam.com/2606/Foam_cuttingPlane.html)

Example usage:

* [movingCone](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoCentralFoam/movingCone)
* [implicit](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPorousSimpleFoam/angledDuct/implicit)
* [movingCone](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/heatTransfer/solidFoam/movingCone)
* [propeller](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/propeller)
* [motorBike](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/motorBike)
