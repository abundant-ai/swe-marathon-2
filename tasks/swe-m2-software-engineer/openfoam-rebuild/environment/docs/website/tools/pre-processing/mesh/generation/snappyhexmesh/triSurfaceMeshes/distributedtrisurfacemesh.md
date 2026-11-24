<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/triSurfaceMeshes/distributedtrisurfacemesh -->

# distributedTriSurfaceMesh

## Description

A distributed version of `triSurfaceMesh`. Usage and specification is the same
as for `triSurfaceMesh`, the difference is in the underlying decomposition of
the surface into equal parts across all processors, and parallelisation of all
queries, e.g. finding the nearest point on the surface, finding intersections.
The routines have been especially written to handle large surfaces with minimal
memory overhead.

Internally, each processor represents the surface using bounding boxes, and
it is therefore beneficial to have similarly sized triangles to minimise the
amount of overlap and processor communication.

## Usage

An example use of the `distributedTriSurfaceMesh`:

## Further information

See also

* [triSurfaceMesh](trisurfacemesh.md)

Tutorials

* [distributedTriSurfaceMesh](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/snappyHexMesh/distributedTriSurfaceMesh)
