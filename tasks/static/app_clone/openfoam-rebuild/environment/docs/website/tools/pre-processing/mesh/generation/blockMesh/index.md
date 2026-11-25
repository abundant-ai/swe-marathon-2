<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/blockMesh/ -->

# blockMesh

## Overview

`blockMesh` is a structured hexahedral mesh generator.

Key features:

* structured hex mesh
* built using blocks
* supports cell size grading
* supports curved block edges

Constraints:

* requires consistent block\-to\-block connectivity
* ordering of points is important

Well suited to simple geometries that can be described by a few blocks, but
challenging to apply to cases with a large number of blocks due to book\-keeping
requirements, i.e. the need to manage point connectivity and ordering.

## Usage

Command line usage:

### Synopsis

```
blockMesh [OPTIONS]

```

#### Arguments

No arguments required.
#### Options

```
-case <dir>       Case directory (instead of current directory)
  -dict <file>      Alternative blockMeshDict
  -merge-points     Geometric point merging instead of topological merging
                    [default for 1912 and earlier].
  -no-clean         Do not remove polyMesh/ directory or files
  -region <name>    Specify mesh region (default: region0)
  -sets             Write cellZones as cellSets too (for processing purposes)
  -time <time>      Specify a time to write mesh to (default: constant)
  -verbose          Force verbose output. (Can be used multiple times)
  -write-vtk        Write topology as VTU file and exit
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-compat      Display compatibility options and exit
  -help-full        Display full help and exit

```

The utility is controlled by a `blockMeshDict` dictionary. By default this is
read from the case `system` directory, but it can also be supplied from
`constant/polyMesh/blockMeshDict`, overridden with `-dict`, or specified per
region with `-region`.

Run `blockMesh -help-full` for the vertex and face numbering diagram used
throughout the dictionary.

## blockMeshDict

The dictionary is split into sections that describe the mesh from geometry
through to boundary assignment. The main entries are:

| Section | Required | Description |
| --- | --- | --- |
| `vertices` | yes | Corner points of all blocks |
| `blocks` | yes | Hex blocks: connectivity, cell counts, grading |
| `edges` | no | Curved or projected edges between vertices |
| `faces` | no | Curved or projected internal/block faces |
| `boundary` | no | Patch assignment for boundary faces |
| `defaultPatch` | no | Name and type for unassigned boundary faces |
| `mergePatchPairs` | no | Pairs of patches to merge into internal faces |
| `scale` / `prescale` | no | Uniform or vector scaling of vertex coordinates |
| `transform` | no | Rotation and translation applied after `prescale` |
| `geometry` | no | Searchable surfaces used by `project` edges and faces |

Vertices and blocks may use named labels (`namedVertices`, `namedBlocks`) and
dictionary variables (`#eval`, `$name`) to keep large cases readable.

### Example

A single\-block channel with wall grading in yyy:

```
scale   1;

vertices
(
    (0 0 0)  // 0
    (1 0 0)  // 1
    (1 1 0)  // 2
    (0 1 0)  // 3
    (0 0 0.1)
    (1 0 0.1)
    (1 1 0.1)
    (0 1 0.1)
);

blocks
(
    hex (0 1 2 3 4 5 6 7) (20 40 1) simpleGrading (1 10 1)
);

boundary
(
    inlet  { type patch; faces ((0 4 7 3)); }
    outlet { type patch; faces ((1 5 6 2)); }
    walls
    {
        type wall;
        faces
        (
            (0 1 5 4)
            (3 7 6 2)
        );
    }
);

```

## Block topology

Each block is a hexahedron defined by eight vertices listed in the `blocks`
entry. Vertices must be ordered consistently so that opposing faces share the
same local point ordering when blocks are connected.

### Vertex numbering

For local vertex labels 0–7:

```
        7 ---- 6
       /|     /|
      4 ---- 5 |
      | 3....| 2
      |/     |/
      0 ---- 1

```

* Vertices 0–3 form the bottom face (zzz\-minimum).
* Vertices 4–7 form the top face (zzz\-maximum).
* Edges run 0–1, 1–2, 2–3, 3–0 on the bottom and 4–5, 5–6, 6–7, 7–4 on the top,
with vertical edges 0–4, 1–5, 2–6, 3–7\.

A block entry has the form:

```
hex (<v0> <v1> ... <v7>) (<nx> <ny> <nz>) <grading-spec>

```

Optional entries between the vertex list and cell counts include a block name
(for use in patch definitions) and a cell zone name.

### Block faces

Each block has six faces with fixed local indices:

| Face index | Direction | Position |
| --- | --- | --- |
| 0, 1 | xxx | left, right |
| 2, 3 | yyy | front, back |
| 4, 5 | zzz | bottom, top |

These indices are used when boundary faces are specified as `(blockIndex faceIndex)` pairs rather than by listing vertex labels directly.

### Multi\-block connectivity

Adjacent blocks must share a complete face: the same vertices (or geometrically
coincident points) in the same order when viewed from outside each block. Where
two blocks meet, their shared face is an internal face and is not listed in
`boundary`.

For complex layouts, give blocks and vertices explicit names:

```
vertices
(
    name v0 (0 0 0)
    name v1 (1 0 0)
    ...
);

blocks
(
    name leftBlock  hex (v0 v1 v2 v3 v4 v5 v6 v7) (10 10 1) simpleGrading (1 1 1)
    name rightBlock hex (v8 v9 v10 v11 v12 v13 v14 v15) (10 10 1) simpleGrading (1 1 1)
);

```

Named labels can be referenced in `boundary`, `edges`, and `faces` entries.

### Curved geometry

By default, block edges are straight lines between vertices. Non\-linear shape is
introduced through optional `edges` and `faces` sections:

* **`arc`** \- circular arc through a specified point.
* **`project`** \- edge projected onto one or more `geometry` surfaces.
* **`projectCurve`** \- edge projected along a surface normal direction.
* **`polyLine`**, **`spline`**, **`line`** \- general edge definitions.

The `faces` section defines non\-planar block faces (for example, projecting a
face onto a sphere or cylinder). Internal faces listed here replace the default
planar face between connected blocks.

## Patches

Boundary conditions are applied to patches created from faces that lie on the
exterior of the block assembly. Patch definition is handled in the `boundary`
section (the older `patches` list format is also supported).

Each patch is a sub\-dictionary:

```
<patchName>
{
    type    <patchType>;          // e.g. patch, wall, symmetry, cyclic
    faces   (...);                // list of faces
    // Additional entries for cyclic, cyclicAMI, etc.
}

```

### Assigning faces to patches

Each face in `faces` is either:

1. **A list of four vertex labels** \- must match a boundary face of the block
assembly exactly (order follows the right\-hand rule, looking into the domain).
2. **A `(blockIndex faceIndex)` pair** \- selects local face `faceIndex` (0–5\) on
block `blockIndex`. This is often clearer in multi\-block cases:

```
inlet
{
    type  patch;
    faces ((0 0));   // face 0 of block 0
}

```
3. **A reference to a named block** \- when `namedBlocks` is used:

```
faces ((sideBlock 3));   // face 3 of block "sideBlock"

```

Multiple faces can belong to one patch. Faces not assigned to any patch are
collected into the `defaultPatch` (default name `defaultFaces`, type `empty`).

### Cyclic and coupled patches

Periodic boundaries are defined as pairs of patches in `boundary`. Each patch
specifies its partner with `neighbourPatch`:

```
inlet
{
    type            cyclic;
    neighbourPatch  outlet;
    faces           ((0 5 11 6) (5 4 10 11));
}

outlet
{
    type            cyclic;
    neighbourPatch  inlet;
    faces           ((1 7 8 2) (2 8 9 3));
}

```

Other coupled types (`cyclicAMI`, `cyclicACMI`, etc.) follow the same pattern,
with additional entries such as `transform` where required.

### Merging patch pairs

When two blocks meet at a face that should be internal (not a boundary), define
matching patches on each side and list them in `mergePatchPairs`:

```
boundary
(
    mid6 { type patch; faces ((0 0)); }   // face 0 of block 0
    mid7 { type patch; faces ((1 1)); }   // face 1 of block 1
);

mergePatchPairs
(
    (mid6 mid7)
);

```

During mesh generation, `blockMesh` merges each listed pair into a single
internal face set and removes the empty patches. This is the usual way to join
blocks that share a conformal interface without exposing that interface as a
boundary patch.

## Grading

Grading controls how cell sizes vary along each direction within a block. It is
specified per block as the last entry in the `blocks` line.

### Expansion ratio

The basic grading parameter is the **expansion ratio**: the ratio of end cell
length to start cell length along a direction. A value of:

* `1` \- uniform spacing.
* `> 1` \- cells grow in the positive local direction.
* `< 0` \- treated as the inverse ratio (cells grow in the negative direction).

For wall\-bounded flows, a ratio of 10 near a wall with `simpleGrading (1 10 1)`
produces finer cells adjacent to the wall in yyy.

### simpleGrading and grading

`simpleGrading` (or the equivalent keyword `grading`) applies one expansion
ratio per coordinate direction. The list may contain 1, 3, or 12 values:

| List length | Effect |
| --- | --- |
| 1 | Same ratio in xxx, yyy, and zzz |
| 3 | Ratios for xxx, yyy, and zzz respectively |
| 12 | Individual ratio for each of the 12 block edges |

With three values, the ratio for a direction is applied uniformly to all four
edges in that direction.

```
hex (0 1 2 3 4 5 6 7) (20 40 1) simpleGrading (1 10 1)
hex (0 1 2 3 4 5 6 7) (20 40 1) grading (1 10 1)      // equivalent

```

Matching expansion ratios on adjacent blocks at a shared face keeps cell sizes
continuous across block interfaces (for example, `10` on one block and `-10` on
its neighbour in the same direction).

### edgeGrading

`edgeGrading` sets the expansion ratio independently for each of the 12 edges.
The list contains 12 values in edge order:

| Edge indices | Direction |
| --- | --- |
| 0–3 | xxx (bottom front, bottom back, top back, top front) |
| 4–7 | yyy (bottom left, bottom right, top right, top left) |
| 8–11 | zzz (front left, front right, back right, back left) |

```
hex (0 1 2 3 4 5 6 7) (40 10 10)
edgeGrading
(
    4  4  4  4    // x-edges
    1  1  1  1    // y-edges
    1  1  1  1    // z-edges
);

```

Use `edgeGrading` when different edges in the same direction need different
spacing (for example, grading toward two walls at opposite ends of a block).

### Multi\-section grading

Each edge (or direction, when using a single value) can be split into multiple
sections with independent spacing. A section is defined by three numbers:

```
(blockFraction nDivFraction expansionRatio)

```

* `blockFraction` \- fraction of the block length occupied by the section.
* `nDivFraction` \- fraction of the cell divisions allocated to the section.
* `expansionRatio` \- cell growth rate within the section.

When only one number is given, it is interpreted as a uniform expansion ratio
(`blockFraction` and `nDivFraction` default to 1\). Multiple sections on one edge
are given as a list:

```
simpleGrading
(
    1
    ((0.3 0.3 1) (0.7 0.7 10))
    1
)

```

This allocates 30% of the yyy divisions to a uniform section and 70% to a graded
section with expansion ratio 10\.

## Further information

Example usage:

* Tutorials: [blockMesh](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/blockMesh)
* Annotated dictionary: [blockMeshDict](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/etc/caseDicts/annotated/blockMeshDict)
