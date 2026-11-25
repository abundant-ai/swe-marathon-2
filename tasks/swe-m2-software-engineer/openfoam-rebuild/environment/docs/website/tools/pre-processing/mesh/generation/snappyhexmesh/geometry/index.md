<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/geometry/ -->

# Geometry

The `geometry` dictionary describes all input geometry required by
`snappyHexMesh`:

* the surface to conform to, e.g. triangulated surfaces and analytical shapes
* regions for volumetric or surface refinement
* setting constraints on internal faces to generate face sets or face zones for
regions

The geometry section can describe triangulated surfaces or
[searchable objects](index.md#searchable-objects). A simple
definition may take the form:

```
geometry
{
    sphere.stl  // name of the geometrical entity
    {
        type            triSurfaceMesh;
    }

    myBox       // name of the geometrical entity
    {
        type            searchableBox;
        min             (1.5 1 -0.5);
        max             (3.5 2 0.5);
    }
};

```

## Triangulated surfaces

Triangulated surfaces must be located in the `$FOAM_CASE/constant/triSurface`
directory. The following formats are supported:

* **stl** \- Stereolithography ASCII
* **stlb** \- Stereolithography binary
* **obj** \- Wavefront object
* **vtk** \- Legacy Visualisation Toolkit (VTK)
* **ftr** \- OpenFOAM triangulated format
* **ac**, **smesh**, **tri** and **dx**

Some formats support multiple regions, e.g. 'SOLID' in the *stl*
format. Each surface and region in a surface becomes a separate
patch in the final mesh.

* [distributedTriSurfaceMesh](../triSurfaceMeshes/distributedtrisurfacemesh.md)
* [triSurfaceMesh](../triSurfaceMeshes/trisurfacemesh.md)

## Searchable objects

These objects define analytical shapes, and are treated similarly to
[triangulated surfaces](index.md#triangulated-surfaces),
e.g. to define the geometry to mesh or refinement regions.

Options:

* [searchableBox](../searchableObjects/searchablebox.md)
* [searchableCone](../searchableObjects/searchablecone.md)
* [searchableCylinder](../searchableObjects/searchablecylinder.md)
* [searchableDisk](../searchableObjects/searchabledisk.md)
* [searchableExtrudedCircle](../searchableObjects/searchableextrudedcircle.md)
* [searchablePlane](../searchableObjects/searchableplane.md)
* [searchablePlate](../searchableObjects/searchableplate.md)
* [searchableRotatedBox](../searchableObjects/searchablerotatedbox.md)
* [searchableSphere](../searchableObjects/searchablesphere.md)
* [searchableSurfaceCollection](../searchableObjects/searchablesurfacecollection.md)
* [searchableSurfaceWithGaps](../searchableObjects/searchablesurfacewithgaps.md)
