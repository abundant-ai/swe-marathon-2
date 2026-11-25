<!-- https://doc.openfoam.com/2606/tools/processing/mesh-motion/ -->

# Mesh motion

Dynamic mesh functionality is categorised by the terminology:

* motion: geometry change only
* topology change: e.g. cell splitting

## Usage

Mesh motion is controlled via the `dynamicMeshDict` located in the `constant`
directory. For a list of solver applications that include mesh motion
capabilities see [here](../solvers.md#capability-matrix).
The type of motion is set according to the
`dynamicFvMesh` entry, e.g.

```
dynamicFvMesh       <type>;

```

Options include:

All the solvers tagged with *dynamic mesh* in the
[Capability matrix](../solvers.md#capability-matrix) support
mesh motion as well as topology changes

* for geometry change only specify in the `dynamicMeshDict`:

```
dynamicFvMesh   dynamicMotionSolverFvMesh

```

* this particular mesh type reads entries to select the actual motion solver to
use, e.g.:

```
motionSolverLibs ("libfvMotionSolvers.so");
motionSolver displacementSBRStress;
...

```

* the actual motion solver might require a field with initial and boundary
conditions, e.g. `0/pointDisplacement` and entries in the `fvSolution`,
`fvSchemes` dictionaries.

* *None*
