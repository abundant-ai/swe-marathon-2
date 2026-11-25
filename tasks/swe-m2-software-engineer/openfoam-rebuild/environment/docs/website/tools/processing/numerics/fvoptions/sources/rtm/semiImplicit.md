<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/semiImplicit -->

# Semi implicit source

## Properties

A typical transport equation takes the form:

DDtx\=S(x) \\frac{D}{Dt}x \= S(x)DtD​x\=S(x)
where the source, S(x)S(x)S(x), is decomposed into explicit and (linearised)
implicit contributions

S(x)\=Su⏟explicit\+Spx⏟implicit S(x) \= \\underbrace{S\_u}\_{\\mathrm{explicit}} \+ \\underbrace{S\_p x}\_{\\mathrm{implicit}}S(x)\=explicitSu​​​\+implicitSp​x​​
## Usage

The source is available as a general option, specified using:

```
generalSource
{
    type            <type>SemiImplicitSource;

    ...

    volumeMode      absolute; // absolute | specific

    injectionRateSuSp
    {
        <field>           (<explicit value> <implicit coefficient>);
        ...
    }
}

```

Where `<type>` is a primitive field type, e.g. `scalar`,
`vector`, `tensor`. As an example, a scalar source applied to the
k and epsilon turbulence equations could take the form:

```
scalarSource
{
    type            scalarSemiImplicitSource;
    duration        1000.0;
    selectionMode   all;

    volumeMode      absolute;

    injectionRateSuSp
    {
        k           (30.7 0);
        epsilon     (1.5  0);
    }
}

```

## Further information

Tutorials

* [filter](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/reactingParcelFoam/filter)
* [TJunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunction)
* [planarPoiseuille](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/laminar/planarPoiseuille)
* [injection](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/reactingTwoPhaseEulerFoam/laminar/injection)

Source code

* [semiImplicitSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/general/semiImplicitSource)
