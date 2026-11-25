<!-- https://doc.openfoam.com/2606/tools/pre-processing/surface/surfaceInertia -->

# surfaceInertia

## Overview

The `surfaceInertia` utility determines the following properties of a
user\-supplied surface file:

* inertia tensor for the thin shell or solid body enclosed by the surface;
* principal axes; and
* moments.

## Usage

### Synopsis

```
surfaceInertia [OPTIONS] <input>

```

#### Examples

```
surfaceInertia -referencePoint '(0 0 1)' surface.stl

```

### Input

#### Arguments

```
<input>           The input surface file

```

#### Options

```
-case <dir>       Case directory (instead of current directory)
  -density <scalar>
                    Specify density, kg/m3 for solid properties, kg/m2 for
                    shell properties
  -referencePoint <vector>
                    Inertia relative to this point, not the centre of mass
  -shellProperties  Inertia of a thin shell
  -doc              Display documentation in browser
  -help             Display short help and exit
  -help-full        Display full help and exit

```

#### Files

No file input required.

#### Fields

No field input required.

### Output

#### Logs

| Property | Type |
| --- | --- |
| Mass of the surface | scalar |
| Centre of mass of the surface | vector |
| Surface area | scalar |
| Inertia tensor around centre of mass | tensor |
| Eigen values \- principal moments | vector |
| Eigen vectors \- principal axes | vectors |
| Transform tensor from reference state (orientation) | tensor |

#### Files

| Property | Description | Path | Type |
| --- | --- | --- | --- |
| `axes.obj` | Writes scaled principal axes at centre of mass of the surface | `<case>/` | `obj` |

#### Fields

No field output.

## Method

The inertia of the surface or the volume is evaluated as follows.

### Shell

The first step is to compute the centre of mass, cmc\_mcm​:

cm\=∑i\=1n∣St,i∣ct,i∑i\=1n∣St,i∣,c\_m \= \\frac{\\sum\_{i\=1}^{n} \| S\_{t,i} \| c\_{t,i}}{\\sum\_{i\=1}^{n} \| S\_{t,i} \|},cm​\=∑i\=1n​∣St,i​∣∑i\=1n​∣St,i​∣ct,i​​,
where StS\_tSt​ is the triangle area and nnn the number of triangles in the
surface.

The tensorial inertia, JJJ, around the centre of mass determined using:

J\=∑i\=1nJt,i,J \= \\sum\_{i\=1}^{n} J\_{t,i},J\=i\=1∑n​Jt,i​,
where JtJ\_tJt​ is the inertia of a triangle.

### Solid

The calculation follows the procedure from the
[Geometric Tools](https://www.geometrictools.com) library. Further details can
be found in [15](../../../references.md#eberly_polyhedral_2009).

## Further information

Tutorial:

* *None*

Source code:

* [surfaceInertia](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/surface/surfaceInertia)
* [momentOfInertia](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/meshTools/momentOfInertia)

**History:** Introduced in version [1\.7\.0](https://www.openfoam.com/news/main-news/openfoam-1.7.0)
