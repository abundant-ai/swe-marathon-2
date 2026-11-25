<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/utilities/solverInfo -->

# solverInfo

The `solverInfo` function object reports the solver performance information for
a list of fields

* residual fields
* solver type
* initial residual
* final residual
* number of solver iterations
* convergence flag

## Usage

The `solverInfo` function object is specified using:

```
solverInfo
{
    type            solverInfo;
    libs            ("libutilityFunctionObjects.so");
    ...
    fields          (U p);
    writeResidualFields yes;
}

```

## Sample output

Solver information is written to the directory according to the
[executeControl](../index.md#usage-run-time-control)
settings:

```
$FOAM_CASE/postProcessing/<functionObject>/<timeDir>

```

An example output is shown below

```
# Solver information
# Time          p_rgh_solver    p_rgh_initial   p_rgh_final     p_rgh_iters     p_rgh_converged
50              GAMG            9.294030e-03    4.311920e-05    4               1
100             GAMG            1.168520e-02    3.014190e-05    3               1
150             GAMG            6.986510e-03    1.489130e-05    3               1
200             GAMG            6.059480e-03    5.917190e-05    2               1
...

```

If the `writeResidualFields` is active, residual fields will be output according
to the [writeControl](../index.md#usage-run-time-control) settings.

## Stored properties

### Reduced data

The following data are stored by the function object, and can be used by other
function objects:

* `<field-name><component>_initial` : initial residual
* `<field-name><component>_final` : final residual
* `<field-name><component>_iters` : number of solver iterations

## Further information

Source code:

* [solverInfo](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/utilities/solverInfo)

API:

* [Foam::functionObjects::solverInfo](https://api.openfoam.com/2606/Foam_functionObjects_solverInfo.html)

Related:

* [Solver residual calculation](../../../processing/numerics/solvers/residuals.md)

**History:** Introduced in version [v3\.0\+](https://www.openfoam.com/news/main-news/openfoam-v3.0+)
