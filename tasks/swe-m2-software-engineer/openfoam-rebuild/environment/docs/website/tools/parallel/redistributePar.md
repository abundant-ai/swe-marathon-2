<!-- https://doc.openfoam.com/2606/tools/parallel/redistributePar -->

# redistributePar

## Overview

The `redistributePar` utility takes an existing case and redistributes its
mesh and fields according to the settings of the
`<case>/system/decomposeParDict` file.

The utility must be run in parallel

Key features:

* Enables straightforward repartitioning of mesh and fields
* Can be used to decompose and reconstruct cases in place of `decomposePar` and
`reconstructPar`, `reconstructParMesh`
* Combines reconstructing mesh with reconstructing fields, i.e. no need for
`reconstructParMesh` after parallel mesh generation
* Runs fully parallel (if supported by the `fileHandler`)

Constraints:

* Must be used on the maximum number of processors
* To run on distributed systems, the utility must be run locally and then the
resulting processor directories copied manually to the remote system(s).
(24\.04\.2023 this limitation is under development)

## Usage

```
redistributePar [OPTIONS]

```

To decompose the case in parallel

```
mpirun -np 2 redistributePar -decompose -parallel

```

To reconstruct the case in parallel

```
mpirun -np 2 redistributePar -reconstruct -parallel

```

To change the partitioning to a new `decomposeParDict`, e.g. number of
processors or type of partitioning:

Contents of original decomposeParDict:

```
numberOfSubdomains 6;

method          hierarchical;

coeffs
{
    n           (6 1 1);
}

```

Contents of new decomposeParDict:

```
numberOfSubdomains 24;

method        scotch;

```

Note that the number of subdomains has increased from 6 to 24, and the method
changed from `hierarchical` to `scotch`. The new settings are applied by
executing:

```
mpirun -np 24 redistributePar -parallel

```

## Further information

Example usage:

* decomposing using `collated` output file format:

```
mpirun -np 2 redistributePar -decompose -fileHandler collated -parallel

```

Tutorials:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/parallel/cavity)
* [filter](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/parallel/filter)
* [fileHandler](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/IO/fileHandler)

Source code

* [redistributePar](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/parallelProcessing/redistributePar)
