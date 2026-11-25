<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/ -->

# Linear equation solvers

## Introduction

This section describes the linear solver options available to solve the matrix
system

Ax\=b \\mat{A} \\vec{x} \= \\vec{b}Ax\=b
where:

A\\mat{A}A
: coefficient matrix

x\\vec{x}x
: vector of unknowns

b\\vec{b}b
: source vector

If the coefficient matrix only has values on its diagonal, the solution vector
can be obtained inverting the matrix system:

x\=A−1b \\vec{x} \= \\mat{A}^{\-1} \\vec{b}x\=A−1b
Where the inverse of the diagonal matrix is simply:

A−1\=1diag(A) \\mat{A}^{\-1} \= \\frac{1}{\\mathrm{diag}(\\mat{A})}A−1\=diag(A)1​
This is available as the `diagonalSolver`. More typically the matrix cannot be
inverted easily and the system is solved using iterative methods, as described
in the following sections.

## Options

Solver options include:

* [Smooth](smooth/index.md)
* [Conjugate Gradient](cg/index.md)
* [Multigrid](multigrid/index.md)

## Solver control

* [Under relaxation](under-relaxation.md)
* [Residuals](residuals.md)
* [Case termination](case-termination.md)

## Common usage

* `minIter`: minimum number of solver iterations
* `maxIter`: maximum number of solver iterations
* `nSweeps`: number of solver iterations between checks for solver convergence

## Implementation details

### Matrix structure

Matrix coefficients are stored in upper\-triangular order

* neighbour cell index always higher than owner cell index across a face
* when looping over cell faces, the face index increases with increasing cell
index
* for the 1\-D case, if cell index 0 is at the boundary, this equates to a
monotonic increase in cell numbers, i.e. defines a continuous sweep across
the 1\-D region
* used in [Gauss\-Seidel](smooth/rtm/gaussSeidel.md)
method

## Further information

* [Source documentation](https://api.openfoam.com/2606/grpLduMatrix.html)
