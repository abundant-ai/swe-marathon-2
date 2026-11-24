<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/snappyhexmesh/meshquality -->

# Mesh quality

The `meshQualityDictionary` dictionary is used to define the values of many
extrema encountered during the meshing process to ensure that the resulting mesh
is of sufficient quality for subsequent calculation. The limits predominantly
affect feature conformance, i.e. regions most likely to incur local mesh
distortion. If the mesh violates any of the limiting values it attempts to
re\-apply the offending changes with updated settings for additional cycles.
This is an override of the mesh quality settings when the
[nRelaxedIter](layers.md#keywords-nRelaxedIter) has been
reached. Values include:

## Keywords

---

### maxNonOrtho \[scalar]

Maximum face non\-orthogonality angle \[deg]: the angle made by the vector
between the two adjacent cell centres across the common face and the face normal

```
maxNonOrtho             65;

```

---

### maxBoundarySkewness \[scalar]

Maximum boundary skewness:

```
maxBoundarySkewness     20;

```

---

### maxInternalSkewness \[scalar]

Maximum internal face skewness:

```
maxInternalSkewness     4;

```

---

### maxConcave \[scalar]

Maximum cell concavity \[deg]:

```
maxConcave              80;

```

---

### minVol \[scalar]

Minimum cell pyramid volume \[m3^33]:

```
minVol                  1e-13;

```

---

### minTetQuality \[scalar]

Minimum tetrahedron quality:

```
//  1e-15 (small positive) to enable tracking
// -1e+30 (large negative) for best layer insertion
minTetQuality           1e-15;

```

---

### minVolCollapseRatio \[scalar]

minVolCollapseRatio:

```
// if >0 : preserve single cells with all points on the surface if the
// resulting volume after snapping (by approximation) is larger than
// minVolCollapseRatio times old volume (i.e. not collapsed to flat cell).
//  If <0 : delete always.
//minVolCollapseRatio   0.5;

```

---

### minArea \[scalar]

Minimum face area \[m2^22]: A negative value to bypass this metric

```
minArea                 -1;

```

---

### minTwist \[scalar]

Minimum twist:

```
minTwist                0.02;

```

---

### minDeterminant \[scalar]

Minimum cell determinant:

```
minDeterminant          0.001;

```

---

### minFaceWeight \[scalar]

Minimum face interpolation weight

```
minFaceWeight           0.05;

```

---

### minFaceFlatness \[scalar]

minFaceFlatness: Optional

```
minFaceFlatness         -1;

```

---

### minVolRatio \[scalar]

minVolRatio:

```
minVolRatio             0.01;

```

---

### minTriangleTwist \[scalar]

minTriangleTwist:

```
minTriangleTwist        -1;

```

---

### nSmoothScale \[scalar]

Smoothing iterations. Used in combination with [errorReduction](meshquality.md#keywords-errorReduction):

```
nSmoothScale            4;

```

---

### errorReduction \[scalar]

Error reduction. Used in combination with [nSmoothScale](meshquality.md#keywords-nSmoothScale)

```
errorReduction          0.75;

```

---

### relaxed \[dictionary]

Any of the mesh quality controls can be relaxed by adding the appropriate
entry to the `relaxed` dictionary, e.g.

```
relaxed
{
    maxNonOrtho             75;
}

```
