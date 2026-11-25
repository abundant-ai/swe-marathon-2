<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/manipulation/topoSet -->

# topoSet

## Overview

The `topoSet` utility is used to manipulate cell, face and point sets and zones,
to define regions for, e.g. post\-processing or sub\-models including porous
media, multiple reference frame (MRF) models etc.

Utilities such as [blockMesh](../generation/blockMesh/index.md) and
[snappyHexMesh](../generation/snappyhexmesh.md) can generate sets and zones directly.

## Usage

The utility is executed by:

```
topoSet [OPTIONS]

```

The full set of options are:

```
Usage: topoSet [OPTIONS]
Options:
  -case <dir>       Case directory (instead of current directory)
  -constant         Include 'constant/' dir in the times list
  -decomposeParDict <file>
                    Alternative decomposePar dictionary file
  -dict <file>      Alternative topoSetDict
  -latestTime       Select the latest time
  -noSync           Do not synchronise selection across coupled patches
  -noZero           Exclude '0/' dir from the times list
  -parallel         Run in parallel
  -region <name>    Specify mesh region (default: region0)
  -time <ranges>    List of ranges. Eg, ':10,20 40:70 1000:', 'none', etc
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-full        Display full help and exit

Operates on cellSets/faceSets/pointSets through a dictionary, normally
system/topoSetDict

Using: OpenFOAM-v2606 (2606) - visit www.openfoam.com
Build: _481094fdf3-20260618
Arch:  LSB;label=32;scalar=64

```

By default, the utility is controlled using a `<case>/system/topoSetDict`
dictionary, where manipulations are specified as a list of operations that are
applied in order.

```
actions
(
    {
        name    <name-1>;
        type    <set-type>;
        action  <action>;
        source  <source-type>;

        // Additional <source-type> information
    }

    {
        name    <name-2>;
        type    <set-type>;
        action  <action-type>;
        source  <source-type>;

        // Additional <source-type> information
    }

    ...
);

```

The `<set-type>` value defines the set type to operate on, i.e.:

* points: `pointSet`, `pointZoneSet`
* faces: `faceSet`, `faceZoneSet`
* cells: `cellSet`, `cellZoneSet`

The `<action-type>` value defines the how the set is to be manipulated by the
set defined the `<source-type>`, i.e.:

* add
* subtract
* new
* subset
* invert
* clear
* remove
* list
* ignore
* delete

The `<source-type>` is specific to the `<set-type>`, where options include

**pointSet**

* `boxToPoint` : select points inside bound box(es)
* `cellToPoint` : select points from cell set(s)
* `clipPlaneToPoint` : select points above a plane
* `cylinderToPoint` : select points in a cylinder or annulus
* `faceToPoint` : select points in face set(s)
* `labelToPoint` : select points from a list of point indices
* `nearestToPoint` : select points closest to a set of points
* `pointToPoint` : select points in point set(s)
* `searchableSurfaceToPoint` : select points enclosed by a `searchableSurface`
* `setToPointZone` : convert a `pointSet` to a `pointZone`
* `sphereToPoint` : select points within a bounding sphere
* `surfaceToPoint` : select points based on relation (distance, inside/outside) to a surface
* `zoneToPoint` : convert a `pointZone` to a `pointSet`

**faceSet**

* `boxToFace` : select faces inside bound box(es)
* `cellToFace` : select faces from cell set(s)
* `clipPlaneToFace` : select faces above a plane
* `cylinderAnnulusToFace` : select faces in a cylinder annulus
* `cylinderToFace` : select faces in a cylinder
* `faceToFace` : select faces in face set(s)
* `holeToFace` : select a set of faces that closes a hole
* `labelToFace` : select faces from a list of face indices
* `normalToFace` : select faces with normal aligned to a specified direction
* `patchToFace` : select faces associated with given patch(es)
* `pointToFace` : select faces connected to any points in point set(s)
* `regionToFace` : select faces in a mesh region
* `searchableSurfaceToFace` : select faces enclosed by a `searchableSurface`
* `sphereToFace` : select faces within a bounding sphere
* `zoneToFace` : convert a `faceZone` to a `faceSet`

**faceZoneSet**

* `cellToFaceZone` : select faces with only 1 neighbour in cell set(s)
* `faceZoneToFaceZone` : select faces in a `faceZone`
* `planeToFaceZone` : select faces based on the adjacent cell centres spanning a given plane
* `searchableSurfaceToFaceZone` : select faces whose cell\-cell centre vector intersects a given `searchableSurface`
* `setAndNormalToFaceZone` : select faces from a `faceSet` where the face normal is aligned to a specified direction
* `setToFaceZone` : convert a `faceSet` to a `faceZone`
* `setsToFaceZone` : convert a list of `faceSet`s to a `faceZone`

**cellSet**

* `boxToCell` : select cells inside bound box(es)
* `cellToCell` : select cells from in cell set(s)
* `clipPlaneToCell` : select cells with centres above a given plane
* `cylinderAnnulusToCell` : select cells in a cylinder annulus
* `cylinderToCell` : select cells in a cylinder
* `faceToCell` : select cells with a face in the given face set(s)
* `faceZoneToCell` : select cells with a face in the given face zone(s)
* `fieldToCell` : select cells based on field values
* `haloToCell` : select cells connected to the outside a `cellSet`
* `labelToCell` : select cells from a list of cell indices
* `nbrToCell` : select cells based on each cell's number of neighbour cells
* `nearestToCell` : select cells with centres nearest to a set of points
* `patchToCell` : select cells adjacent to a lost of patches
* `pointToCell` : select cells with with any points in the given point set(s)
* `regionToCell` : select cells in a mesh region
* `rotatedBoxToCell` : select sells in a rotated box
* `searchableSurfaceToCell` : select cells enclosed by a `searchableSurface`
* `shapeToCell` : select cells based on their shape
* `sphereToCell` : select cells within a bounding sphere
* `surfaceToCell` : select cells based on relation (distance, inside/outside) to
a surface
* `targetVolumeToCell` : selects cells based on a target volume obtained by
sweeping a surface through the mesh
* `zoneToCell` : converts a `cellZone` to a `cellSet`

**cellZoneSet**

* `setToCellZone` : converts a `cellSet` to a `cellZone`

## Examples

### Cells

Select all cells in the bounding box defined by the points (0 0 0\) and (1 1 1\):

```
{
    name    box1;
    type    cellSet;
    action  new;
    source  boxToCell;
    min     (0 0 0);
    max     (1 1 1);
}

```

Select all cells defined by `p` field in the range 0 and 10:

```
{
    name    field1;
    type    cellSet;
    action  new;
    source  fieldToCell;
    field   p;
    min     0;
    max     10;
}

```

Remove the set of cells given by cellZone `zone1` from cell set `zone2`

```
{
    name    zone2;
    type    cellSet;
    action  subtract;
    source  zoneToCell;
    zone    zone1;
}

```

## Further information

Example usage:

* Tutorials:
	+ [compartmentFire](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/compartmentFire)
	+ [simpleCar](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/simpleFoam/simpleCar)
	+ [filter](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/filter)

Source code

* [topoSet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/mesh/manipulation/topoSet)
