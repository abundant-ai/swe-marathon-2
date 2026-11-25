<!-- https://doc.openfoam.com/2606/tools/processing/numerics/schemes/wall-distance/rtm/Poisson -->

# Poisson wall distance

## Properties

Calculation of approximate distance to nearest patch for all cells and
boundary by solving a Poisson equation.

## Usage

The scheme is specified using:

```
wallDist
{
    method          Poisson;
}

```

This requires the additional entry in the
[divSchemes](../../divergence.md) sub\-dictionary in the
[fvSchemes](../../../../../../fundamentals/case-structure/fvschemes.md) file, e.g.:

```
laplacianSchemes
{
    laplacian(yPsi) <laplacian scheme>;
}

```

An solver entry for the `yPsi` variable is also required for the
[fvSolution](../../../../../../fundamentals/case-structure/fvsolution.md) file, e.g.

```
yPsi
{
    solver          <solver>;
    ...
    tolerance       1e-5;
    relTol          0;
}

```

## Further information

Source code

* [Foam::patchDistMethods::Poisson](https://api.openfoam.com/2606/Foam_patchDistMethods_Poisson.html)

References

* *Spalding* [71](../../../../../../references.md#spalding_calculation_1994)
* *Fares and Schroder* [17](../../../../../../references.md#fares_differential_2002)
* *Tucker* [80](../../../../../../references.md#tucker_differential_2003)
