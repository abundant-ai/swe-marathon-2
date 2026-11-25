<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/wall-distance/ -->

# Wall distance calculation methods

## Usage

Wall distance properties are input in the [fvSchemes](../../../../../fundamentals/case-structure/fvschemes.md) file
under the `wallDist` sub\-dictionary using the syntax:

```
wallDist
{
    method          <method>;
}

```

## Options

The wall distance field can be written using the `checkMesh` utility using the
`writeAllFields` option.

* [Directional mesh\-wave wall distance](rtm/directionalMeshWave.md)
* [Mesh\-wave wall distance (default)](rtm/meshWave.md)
* [Poisson wall distance](rtm/Poisson.md)

## Further information

Source code:

* [wallDist](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fvMesh/wallDist/wallDist)
* [patchDistMethod](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fvMesh/wallDist/patchDistMethods/patchDistMethod)

API:

* [Foam::wallDist](https://api.openfoam.com/2606/Foam_wallDist.html)
* [Foam::patchDistMethod](https://api.openfoam.com/2606/Foam_patchDistMethod.html)
