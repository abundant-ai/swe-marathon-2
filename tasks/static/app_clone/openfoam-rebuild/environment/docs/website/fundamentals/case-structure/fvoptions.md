<!-- https://doc.openfoam.com/2606/fundamentals/case-structure/fvoptions -->

# fvOptions

Many OpenFOAM applications contain equation systems that can be manipulated at
run time via user\-specified finite volume options, given by the shorthand
`fvOptions`. These provide, e.g. additional source/sink terms, or enforce
constraints.

Options include:

* [Sources](../../tools/processing/numerics/fvoptions/sources.md)
* [Corrections](../../tools/processing/numerics/fvoptions/corrections.md)
* [Constraints](../../tools/processing/numerics/fvoptions/constraints.md)

## Further information

Source code:

* [fvOptions](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions)

API:

* [grpFvOptions](https://api.openfoam.com/2606/grpFvOptions.html)
