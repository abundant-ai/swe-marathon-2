<!-- https://doc.openfoam.com/2606/tools/processing/solvers/pressure-velocity/simple -->

# SIMPLE algorithm

noteThis page is under construction.

## SIMPLE

* \<B\>S\</B\>emi\-\<B\>I\</B\>mplicit \<B\>M\</B\>ethod for \<B\>P\</B\>ressure \<B\>L\</B\>inked
\<B\>E\</B\>quations
* By *Caretto et al.* [9](../../../../references.md#caretto_two_1972)

The sequence for each iteration follows:

1. Advance to the next iteration t\=tn\+1t \= t^{n \+ 1}t\=tn\+1
2. Initialise un\+1\\u^{n\+1}un\+1 and pn\+1p^{n\+1}pn\+1 using latest available values of
u\\uu and ppp
3. Construct the
[momentum equations](index.md#eqn-solver-momentum)
4. Under\-relax the
[momentum matrix](index.md#eqn-solver-matrix-composition)
5. Solve the momentum equations to obtain a prediction for un\+1\\u^{n\+1}un\+1
6. Construct the
[pressure equation](index.md#eqn-solver-pressure)
7. Solve the pressure equation for pn\+1p^{n\+1}pn\+1
8. [Correct the flux](index.md#eqn-solver-flux-corrector)
for ϕn\+1\\phi^{n\+1}ϕn\+1
9. Under\-relax pn\+1p^{n\+1}pn\+1
10. [Correct the velocity](index.md#eqn-solver-velocity-corrector%22)

```
for $$ \u^{n+1} $$

```

11. If not converged, go back to step 2

## SIMPLEC

* By *Van Doormaal and Raithby* [82](../../../../references.md#van_doormaal_enhancements_1984)
