<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/searchableObjects/searchablesurfacewithgaps -->

# searchableSurfaceWithGaps

A *searchableSurface* that employs multiple slightly perturbed underlying
surfaces to help prevent the mesh from leaking though small gaps.

## Usage

The surface must be defined in the
[Geometry](../geometry/index.md) dictionary, to which a
perturbation is applied to identify (and close) gaps.

```
sphere.stl
{
    type            triSurfaceMesh;
}

sphere
{
    type            searchableSurfaceWithGaps;

    // Underlying surface
    surface         sphere.stl;

    // Perturbation distance
    gap             1e-3;
}

```
