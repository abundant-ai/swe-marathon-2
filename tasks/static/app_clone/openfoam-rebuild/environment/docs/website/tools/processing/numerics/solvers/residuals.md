<!-- https://doc.openfoam.com/2606/tools/processing/numerics/solvers/residuals -->

# Residuals

## Tolerances

Equation tolerances are described in terms of *absolute* and *relative*
quantities:

```
tolerance       1e-6;
relTol          0.1;

```

If the equation initial residual satisfies either of the specified values,
the system of equations are assumed solved and will not be evolved.

## Calculation

The residual calculation is solver\-specific. However, the general approach
follows:

For a matrix system

Ax\=b, \\mat{A} \\vec{x} \= \\vec{b},Ax\=b,
the residual is defined as

r\=b−Ax. \\vec{r} \= \\vec{b} \- \\mat{A} \\vec{x}.r\=b−Ax.
We then apply residual scaling using the following normalisation procedure:

n\=∑(∣Ax−Ax‾∣\+∣b−Ax‾∣) n \= \\sum \\left(
 \\mag{\\mat{A}\\vec{x} \- \\mat{A}\\av{\\vec{x}}}
 \+ \\mag{\\vec{b} \- \\mat{A}\\av{\\vec{x}}}
 \\right)n\=∑(∣Ax−Ax∣\+∣b−Ax∣)
where x‾\\av{\\vec{x}}x is the average of the solution vector. The
scaled residual is finally given by:

r\=1n∑∣b−Ax∣. r \= \\frac{1}{n} \\sum \\mag{\\vec{b} \- \\mat{A} \\vec{x}}.r\=n1​∑∣b−Ax∣.
This form leads to a normalised residual of 1 for uniform systems, i.e. where
x\=x‾\\vec{x} \= \\av{\\vec{x}}x\=x. However, this also shows that if the
initial solution changes, e.g. using non\-uniform conditions, the normalisation
also changes, leading to a different convergence history.
