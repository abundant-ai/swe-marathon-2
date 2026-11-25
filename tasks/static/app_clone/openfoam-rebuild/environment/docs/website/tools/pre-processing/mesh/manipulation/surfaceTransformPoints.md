<!-- https://doc.openfoam.com/2606/tools/pre-processing/mesh/manipulation/surfaceTransformPoints -->

# surfaceTransformPoints

## Overview

The `surfaceTransformPoints` utility performs geometric transformations on
surfaces, e.g. scale, translate, rotate, and convert between surface formats.
It is similar to the `transformPoints` utility.

## Usage

### Synopsis

```
surfaceTransformPoints [OPTIONS] <input> <output>

```

#### Examples

Translate all points by the vector (0 0 1\):

```
surfaceTransformPoints -translate '(0 0 1)' input.obj output.obj

```

Scale a surface to convert from \[mm] to \[m] and recentre:

```
surfaceTransformPoints -recentre -scale 0.001 input.stl output.stl

```

### Input

#### Arguments

```
<input>           The input surface file
  <output>          The output surface file

```

#### Options

```
-auto-centre      Use bounding box centre as centre for rotations
  -case <dir>       Case directory (instead of current directory)
  -centre <point>   Use specified <point> as centre for rotations
  -cylToCart <(originVec axisVec directionVec)>
                    Tranform cylindrical coordinates to cartesian coordinates
  -read-format <type>
                    Input format (default: use file extension)
  -read-scale <scalar | vector>
                    Uniform or non-uniform input scaling
  -recentre         Recentre the bounding box before other operations
  -rollPitchYaw <vector>
                    Rotate by '(roll pitch yaw)' degrees
  -rotate <(vectorA vectorB)>
                    Rotate from <vectorA> to <vectorB> - eg, '((1 0 0) (0 0 1))'
  -rotate-angle <(vector angle)>
                    Rotate <angle> degrees about <vector> - eg, '((1 0 0) 45)'
  -rotate-x <deg>   Rotate (degrees) about x-axis
  -rotate-y <deg>   Rotate (degrees) about y-axis
  -rotate-z <deg>   Rotate (degrees) about z-axis
  -translate <vector>
                    Translate by specified <vector> before rotations
  -write-format <type>
                    Output format (default: use file extension)
  -write-scale <scalar | vector>
                    Uniform or non-uniform output scaling
  -yawPitchRoll <vector>
                    Rotate by '(yaw pitch roll)' degrees
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-compat      Display compatibility options and exit
  -help-full        Display full help and exit

```

* The surface format is deduced from the input and output file extensions.
* `roll`\=rotate about x, `pitch`\=rotate about y, `yaw`\=rotate about z.

#### Files

No file input required.

#### Fields

No field input required.

### Output

#### Logs

No log output.

#### Files

| Property | Description | Path | Type |
| --- | --- | --- | --- |
| `<output>` | New surface file | `<case>/` | input type |

#### Fields

No field output.

## Further information

Tutorial:

* [squareBend](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBend)
* [distributedTriSurfaceMesh](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/snappyHexMesh/distributedTriSurfaceMesh)

Source code:

* [surfaceTransformPoints](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/surface/surfaceTransformPoints)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
