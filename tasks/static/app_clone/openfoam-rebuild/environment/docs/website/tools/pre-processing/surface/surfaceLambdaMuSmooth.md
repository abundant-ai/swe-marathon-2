<!-- https://doc.openfoam.com/2606/tools/pre-processing/surface/surfaceLambdaMuSmooth -->

# surfaceLambdaMuSmooth

## Overview

The `surfaceLambdaMuSmooth` utility smooths a given surface by moving point
positions based on the procedure described by Taubin
[76](../../../references.md#taubin_signal_1995).

## Usage

### Synopsis

```
surfaceLambdaMuSmooth [OPTIONS] <input> <lambda> <mu> <iterations> <output>

```

#### Examples

```
surfaceLambdaMuSmooth surface.stl 0.5 0.5 1 output.stl

```

### Input

#### Arguments

```
<input>           The input surface file
  <lambda>          On the interval [0,1]
  <mu>              On the interval [0,1]
  <iterations>      The number of iterations to perform
  <output>          The output surface file

```

#### Options

```
-featureFile <Fix points from a file containing feature points and edges>
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

| Property | Description | Type |
| --- | --- | --- |
| `Faces` | Number of faces on the surface | label |
| `Vertices` | Number of vertices on the surface | label |
| `Bounding Box` | Bounding box of the surface | min/max vector |

#### Files

| Property | Description | Path | Type |
| --- | --- | --- | --- |
| `featureFile` | New surface file | `<case>/` | input type |

#### Fields

No field output.

## Method

The discrete Laplacian is given by

Δxi\=∑j∈i∗wij(xj−xi)\\Delta x\_i \= \\sum\_{j \\in i^{\*}} w\_{ij}(x\_j \- x\_i)Δxi​\=j∈i∗∑​wij​(xj​−xi​)
The weight wijw\_{ij}wij​ is set to the inverse of the number of points surrounding
the point iii, i.e.

wij\=1i∗w\_{ij} \= \\frac{1}{i^{\*}}wij​\=i∗1​
Gaussian filtering is performed iteratively as

xi′\=xi\+λΔxix\_i^{'} \= x\_i \+ \\lambda \\Delta x\_ixi′​\=xi​\+λΔxi​
xi′\=(1−λ)xi\+λΔxix\_i^{'} \= (1 \- \\lambda) x\_i \+ \\lambda \\Delta x\_ixi′​\=(1−λ)xi​\+λΔxi​
xi′\=xi\+μΔxix\_i^{'} \= x\_i \+ \\mu \\Delta x\_ixi′​\=xi​\+μΔxi​
xi′\=(1\+μ)xi−μΔxix\_i^{'} \= (1 \+ \\mu) x\_i \- \\mu \\Delta x\_ixi′​\=(1\+μ)xi​−μΔxi​
For Laplacian smoothing, the μ\\muμ coefficient should be set to zero.

The procedure will move all points by default, and therefore will degrade
features points and lines. To preserve features, the set of points to fix can
be supplied.

Provide an `edgeMesh` file containing points that are not to be moved during
smoothing in order to preserve features.

## Further information

Tutorial:

* *None*

Source code:

* [surfaceLambdaMuSmooth](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/$FOAM_UTILITIES/surface/surfaceLambdaMuSmooth)

**History:** Introduced in version [2\.2\.1](https://www.openfoam.com/news/main-news/openfoam-2.2.1)
