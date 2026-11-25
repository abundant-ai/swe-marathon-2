<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/global -->

# Global settings

## Keywords

### castellatedMesh \[boolean]

Flag to run/skip castellation stage

```
castellatedMesh yes; // no

```

---

### snap \[boolean]

Flag to run/skip snapping stage

```
snap        yes; // no

```

---

### addLayers \[boolean]

Flag to run/skip layer addition stage

```
addLayers   yes; // no

```

---

### singleRegionName \[boolean] OPTIONAL

Single region surfaces get patch names according to the surface only.
Multi\-region surfaces get patch name surface "\_ "region. Default is true

```
singleRegionName  yes; // no

```

---

### mergePatchFaces \[boolean] OPTIONAL

Avoid patch\-face merging. Allows mesh to be used for refinement/unrefinement.
Default is true

```
mergePatchFaces yes; // no

```

---

### keepPatches \[boolean] OPTIONAL

Preserve all generated patches. Default is to remove zero\-sized patches (false).

```
keepPatches     no; // yes

```

---

### mergeTolerance \[scalar]

Merge tolerance. Is fraction of overall bounding box of initial mesh.
Note: the write tolerance needs to be higher than this.

---

## Debugging

---

### debug (label) OPTIONAL

Debug levels to write intermediate mesh data. Use [debugFlags](global.md#debugging-debugFlags)
instead for better control

Example

```
debug     1;

```

---

### debugFlags (List) OPTIONAL

Provides fine\-grain control over the debug output, including:

* `mesh`: write intermediate meshes
* `intersections`: write current mesh intersections as .obj files
* `featureSeeds`: write information about explicit feature edge refinement
* `attraction`: write attraction as .obj files
* `layerInfo`: write information about layers

Example

```
debugFlags
(
    featureSeeds
    attraction
);

```

---

### writeFlags (List) OPTIONAL

Provides fine\-grain control over the write output, including:

* `mesh`: write all mesh information
* `noRefinement`: write mesh without refinement information (level0Edges, surfaceIndex)
* `scalarLevels`: write volScalarField with cellLevel for post\-processing
* `layerSets`: write cellSets, faceSets of faces in layer
* `layerFields`: write a volScalarField for layer coverage

Example

```
writeFlags
(
    scalarLevels
    layerSets
    layerFields     // write volScalarField for layer coverage
);

```

---
