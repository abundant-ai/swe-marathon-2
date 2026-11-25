<!-- https://doc.openfoam.com/2606/tools/processing/solvers/rtm/compressible -->

# Compressible

## Solvers

* [rhoCentralFoam](compressible/rhoCentralFoam.md)
* [rhoPimpleFoam](compressible/rhoPimpleFoam.md)
* [rhoSimpleFoam](compressible/rhoSimpleFoam.md)

## Common options

### Transonic

In the [fvSolution](../../../../fundamentals/case-structure/fvsolution.md)

```
SIMPLE
{
    transonic       yes;
}

```

or

```
PIMPLE
{
    transonic       yes;
}

```

## Further information

* [Source documentation](https://api.openfoam.com/2606/grpIncompressibleSolvers.html)
