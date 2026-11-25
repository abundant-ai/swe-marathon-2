<!-- https://doc.openfoam.com/2606/tools/post-processing/function-objects/field/turbulenceFields -->

# turbulenceFields

## Description

The `turbulenceFields` function object
computes various turbulence\-related quantities that are not typically
output during calculations, including:

* `k`: Turbulent kinetic energy
* `epsilon`: Turbulent kinetic energy dissipation rate
* `omega`: Specific dissipation rate
* `R`: Reynolds stress tensor
* `L`: Integral\-length/Mixing\-length scale
* `I`: Turbulence intensity
* `nuTilda`: Modified turbulent viscosity

Additional field selections for incompressible cases:

* `nut`: Turbulent (edy) kinematic viscosity
* `nuEff`: Effective kinematic viscosity (laminar \+ turbulent contributions)
* `devReff`: Deviatoric stress tensor

Additional field selections for compressible cases:

* `mut`: Turbulent (eddy) dynamic viscosity
* `muEff`: Effective dynamic viscosity (laminar \+ turbulent contributions)
* `alphat`: Thermal eddy diffusivity
* `alphaEff`: Effective eddy thermal diffusivity
* `devRhoReff`: Deviatoric stress tensor

These fields are stored on the mesh database for further post\-processing, and
written as regular volume fields at write intervals.

### Operands

| Operand | Type | Location |
| --- | --- | --- |
| input | \- | \- |
| output file | \- | \- |
| output field | `vol<Type>Field` | `$FOAM_CASE/<time>/<outField>` |

where `<Type>=Scalar/Vector/SphericalTensor/SymmTensor/Tensor`.

## Usage

Example of the `turbulenceFields` function object
by using `functions` sub\-dictionary in `system/controlDict` file:

```
turbulenceFields1
{
    // Mandatory entries (unmodifiable)
    type            turbulenceFields;
    libs            (fieldFunctionObjects);

    // Mandatory entries (runtime modifiable)
    // Either field or fields entries
    fields          (R devRhoReff);
    field           R;

    // Optional (inherited) entries
    region          region0;
    enabled         true;
    log             true;
    timeStart       0;
    timeEnd         1000;
    executeControl  timeStep;
    executeInterval 1;
    writeControl    timeStep;
    writeInterval   1;
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: turbulenceFields | word | yes | \- |
| libs | Library name: fieldFunctionObjects | word | yes | \- |
| fields | Names of fields to store (see below) | wordList | yes | \- |
| field | Name of a field to store (see below) | word | yes | \- |

The inherited entries are elaborated in:

* [functionObject](../index.md)

Example by using the `postProcess` utility:

```
<solver> -postProcess -func turbulenceFields

```

## Sample output

Fields stored on the mesh database with the prefix `turbulenceProperties:`, e.g.

```
turbulenceProperties:mut
turbulenceProperties:R
turbulenceProperties:devRhoReff

```

and written to the standard time directories according to the
[writeControl](../index.md#usage-run-time-control)
setting.

## Further information

Tutorial:

* [cavity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pisoFoam/RAS/cavity)

Source code:

* [turbulenceFields](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/functionObjects/field/turbulenceFields)

API:

* [Foam::functionObjects::turbulenceFields](https://api.openfoam.com/2606/Foam_functionObjects_turbulenceFields.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
