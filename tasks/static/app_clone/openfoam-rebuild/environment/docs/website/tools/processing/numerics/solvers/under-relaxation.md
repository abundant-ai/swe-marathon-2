<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/under-relaxation -->

# Under relaxation

Under relaxation factors are applied to stabilise calculations by limiting the
rate of change of both fields and equations.

## Field under\-relaxation

Qn\=Qo\+α(Q−Qo) Q^n \= Q^o \+ \\alpha \\left( Q \- Q^o \\right)Qn\=Qo\+α(Q−Qo)
## Equation under\-relaxation

The linear solvers require that the coefficient matrix
is at least diagonally equal, and preferably diagonally dominant, i.e. per row,
the magnitude of the diagonal must be greater than or equal to the sum of the
off\-diagonal components.

## Usage

Specified in the [fvSolution](../../../../fundamentals/case-structure/fvsolution.md) file
under the `relaxationFactors` sub\-dictionary

```
relaxationFactors
{
    fields
    {
    }
    equations
    {
    }
}

```

Values relate to

* 0: no under\-relaxation (equivalent to not specified}
* 1: matrix forced to become diagonally equal
