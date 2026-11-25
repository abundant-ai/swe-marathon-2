<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions -->

# Finite volume options

## Introduction

OpenFOAM solver applications typically include core functionality such as
turbulence modelling, heat transfer, and buoyancy effects.

Further flexibility is offered via `fvOptions`\-\-\-a collection of run\-time
selectable finite volume options to manipulate systems of equations by adding
sources/sinks, imposing constraints and applying corrections.

These are specified in the [fvOptions](../../../fundamentals/case-structure/fvoptions.md) file
located in the [FOAMCASE/system](../../../../fundamentals/case−structure/fvoptions.md)or\[FOAM\_CASE/system](../../../../fundamentals/case\-structure/fvoptions.md) or
\[FOAMC​ASE/system](../../../../fundamentals/case−structure/fvoptions.md)or\[FOAM\_CASE/constant](../../../fundamentals/case-structure/fvoptions.md) directories.

## Options

* [Sources](fvoptions/sources/index.md)
* [Constraints](fvoptions/constraints/index.md)
* [Corrections](fvoptions/corrections/index.md)

## Usage

### Selecting the region

The majority of options are applied to collections of mesh cells. These can
be selected according to the entry `selectionMode`, e.g.

```
selectionMode       all;

```

Valid `selectionMode` entries include:

* `all`: all cells
* `cellZone`: cells defined by a cell zone. This requires an additional entry to specify the name of the cell zone, e.g.

```
selectionMode       cellZone;
cellZone            myCellZone;

```

where `myCellZone` is the name of the cell zone

* `cellSet`: cells defined by a cell set. This requires an additional entry
to specify the name of the cell set, e.g.

```
selectionMode       cellSet;
cellSet             myCellSet;

```

where `myCellSet` is the name of the cell set.

* `points`: a list of points. This requires an additional entry to list the
points, e.g.

```
selectionMode       points;
points              ((0 0 0) (1 1 1) (2 2 2));

```
