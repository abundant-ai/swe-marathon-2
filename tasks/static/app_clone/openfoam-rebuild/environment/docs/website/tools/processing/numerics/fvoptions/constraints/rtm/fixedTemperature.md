<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/constraints/rtm/fixedTemperature -->

# Fixed temperature

This constraint will fix the temperature in the energy equation in the mesh
region specified, regardless of incoming flow temperature or local flow
behaviour.

## Properties

Downstream of the constraint the temperature field will continue to develop
normally. Please note this will only affect the temperature field. Other
thermodynamic fields, e.g. density, may still show sensitivity to the local
pressure (if applicable). Note that this constraint will cause a
non\-conservation of energy. No information will be added to the log file other
than the identification of the constraint at the start of the simulation.

## Usage

```
fixedTemperature
{
    type            fixedTemperatureConstraint;
    active          yes;

    selectionMode   cellZone;
    cellZone        porosity;

    mode            uniform;      // uniform or lookup

    // For uniform option
    temperature     constant 500; // fixed temperature with time \[K\]

    // For lookup option
    // T            <Tname>;      // optional temperature field name
}

```

## Further information

Tutorials

* [simplifiedSiwek](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/coalChemistryFoam/simplifiedSiwek)
* [angledDuctExplicitFixedCoeff](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/angledDuctExplicitFixedCoeff)
* [angledDuct](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPorousSimpleFoam/angledDuct)

Source code

* [fixedTemperatureConstraint](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/constraints/derived/fixedTemperatureConstraint)
