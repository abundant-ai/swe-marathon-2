<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/generation/makeFaMesh -->

# makeFaMesh

## Overview

The `makeFaMesh` utility creates finite\-area meshes from volume\-mesh patches.

## Usage

### Synopsis

```
makeFaMesh [OPTIONS]

```

#### Examples

Run `makeFaMesh` and write the mesh as a VTK file for display:

```
makeFaMesh -write-vtk

```

### Input

#### Arguments

No arguments required.
#### Options

```
-allAreas         Use all regions in finite-area regionProperties
  -area-region <name>
                    Specify area-mesh region. Eg, -area-region shell
  -area-regions <wordRes>
                    Use specified area region. Eg, -area-regions film
                    Or from regionProperties.  Eg, -area-regions '(film
                    "solid.*")'
  -case <dir>       Case directory (instead of current directory)
  -decomposeParDict <file>
                    Alternative decomposePar dictionary file
  -dict <file>      Alternative faMeshDefinition
  -dry-run          Create but do not write
  -empty-patch <name>
                    Specify name for a default empty patch
  -no-decompose     Suppress procAddressing creation and field decomposition
                    (parallel)
  -no-fields        Suppress field decomposition (parallel)
  -parallel         Run in parallel
  -region <name>    Specify mesh region (default: region0)
  -write-vtk        Write mesh as a vtp (vtk) file for display or debugging
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-compat      Display compatibility options and exit
  -help-full        Display full help and exit

```

#### Files

The `makeFaMesh` utility is configured using a `<case>/system/faMeshDefinition`,
taking the form:

```
polyMeshPatches             ( <patch1> <patch2> ... <patchN> );

boundary
{
    <faPatch1>
    {
        type                <word>;
        neighbourPolyPatch  <word>;
        ownerPolyPatch      <word>;
    }
}

defaultPatch
{
    name    <word>;
    type    <word>;
}

```

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `polyMeshPatches` | List of volume mesh patches to use as the base of the finite area mesh | `wordRes` | yes | \- |
| `boundary` | Dictionary providing list of edge\-boundary conditions | `dict` | yes | \- |
| `type` | Patch type, e.g. `patch` | `word` | yes | \- |
| `neighbourPolyPatch` | Finite\-volume patch neighbouring the finite\-area | `word` | yes | \- |
| `ownerPolyPatch` | Finite\-volume patch corresponding to the finite\-area patch | `word` | no | \- |
| `defaultPatch` | Dictionary providing characteristics of default patches | `dict` | no | \- |
| `name` | Name of default patches | `word` | yes | \- |
| `type` | Patch type of default patches, e.g. `empty` | `word` | yes | \- |

#### Fields

No field input required.

### Output

#### Logs

No log output.

#### Files

No file output.

#### Fields

The default path to write fields is `<case>/constant/faMesh/`.

| Property | Description | Type |
| --- | --- | --- |
| `faBoundary` | Finite\-area boundary info | `faBoundaryMesh` |
| `faceLabels` | Finite\-area mesh info | `labelList` |

## Further information

Tutorial:

* [faMeshDefinition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/finiteArea/liquidFilmFoam/cylinder/system/finite-area/faMeshDefinition)
* [faMeshDefinition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/acousticFoam/obliqueAirJet/main/system/finite-area/faMeshDefinition)
* [faMeshDefinition](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/filmPanel0/system/finite-area/faMeshDefinition)

Source code:

* [makeFaMesh](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/finiteArea/makeFaMesh)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
