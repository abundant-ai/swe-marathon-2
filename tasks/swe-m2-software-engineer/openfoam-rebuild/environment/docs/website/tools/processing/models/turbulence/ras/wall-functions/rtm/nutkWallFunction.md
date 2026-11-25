<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/wall-functions/rtm/nutkWallFunction -->

# Turbulence viscosity based on turbulence kinetic energy

## Properties

* Uses turbulence kinetic energy, kkk
* Employs a switching behaviour for the turbulence viscosity, νt\\nu\_tνt​

## Usage

The wall function is specified using:

```
wallPatch
{
    type            nutkWallFunction;
    value           XXX;
}

```

## Further information

Source code:

* [Foam::nutkWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_nutkWallFunctionFvPatchScalarField.html)
