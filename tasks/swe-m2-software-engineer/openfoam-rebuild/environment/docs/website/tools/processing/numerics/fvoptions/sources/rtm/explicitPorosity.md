<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/explicitPorosity -->

# Explicit porosity

## Properties

* Provides a wrapper around a run\-time selectable porosity model

## Usage

The option is specified using:

```
porosity1
{
    type            explicitPorositySource;
    selectionMode   cellZone;

    explicitPorositySourceCoeffs
    {
        type            <porosity model>;
        ...
    }
}

```

The `selectionMode` entry should be set to `cellZone`

## Further information

Tutorials

* [angledDuct](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/angledDuct)
* [angledDuctExplicitFixedCoeff](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/angledDuctExplicitFixedCoeff)
* [porousBlockage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/laminar/porousBlockage)
* [filter](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/mesh/parallel/filter)
* [angledDuct](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/angledDuct)

Source code

* [explicitPorositySource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/sources/derived/explicitPorositySource)
