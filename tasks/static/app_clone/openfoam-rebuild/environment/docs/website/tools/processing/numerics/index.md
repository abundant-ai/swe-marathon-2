<!-- https://doc.openfoam.com/2606/tools/processing/numerics/ -->

# Numerics

## Overview

OpenFOAM includes a wide range of solution and scheme controls, specified
via dictionary files in the case `system` sub\-directory. These are described
by:

* [Numerical schemes](schemes/index.md): The treatment of each term in the
system of equations is specified in the
[fvSchemes](../../../fundamentals/case-structure/fvschemes.md) dictionary. This enables
fine\-grain control of e.g. temporal, gradient, divergence and interpolation
schemes.
* [Solution methods](solvers/index.md): Case solution parameters are
specified in the [fvSolution](../../../fundamentals/case-structure/fvsolution.md) dictionary.
These include choice of linear equation solver per field variable, algorithm
controls e.g. number of inner and outer iterations and under\-relaxation.
* [Finite volume options](fvoptions/index.md): Additional run\-time selectable
physical modelling and general finite terms are prescribed in the
[fvOptions](../../../fundamentals/case-structure/fvoptions.md) dictionary, targeting e.g.
acoustics, heat transfer, momentum sources, multi\-region coupling, linearised
sources/sinks and many more

## Topics

* [Overset meshes](overset.md): framework to interpolate between multiple meshes
