<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmPlantCanopyTSource -->

# atmPlantCanopyTSource

## Properties

* The `atmPlantCanopyTSource` applies sources on temperature, i.e. `T`, to
incorporate effects of plant canopy for atmospheric boundary layer modelling.
* The `atmPlantCanopyTSource` can be applied on any RAS turbulence model.
* The `atmPlantCanopyTSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to:

`T`
: Temperature \[K]

Required fields:

`T`
: Temperature \[K]

`qPlant`
: Tree\-height based specific heat flux \[m2^22/s3^33]

## Model equations

The model expression:

fM\+\=αρqplantCp0 f\_M \+\= \\alpha \\rho \\frac{q\_{plant}}{C\_{p\_0}}fM​\+\=αρCp0​​qplant​​
Where:

fMf\_MfM​
: fvMatrix of the temperature field \[K/s]

qplantq\_{plant}qplant​
: Tree\-height based specific heat flux \[m2/s3]

Cp0C\_{p\_0}Cp0​​
: Specific heat capacity \[m2/s2/K]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmPlantCanopyTSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmPlantCanopyTSource;

    atmPlantCanopyTSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Optional entries (unmodifiable)
        rho             rho;
        Cp0             1005.0;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmPlantCanopyTSource | word | yes | \- |
| rho | Name of density field | word | no | rho |
| Cp0 | Specific heat capacity \[m2/s2/K] | scalar | no | 1005\.0 |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmPlantCanopyTSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmPlantCanopyTSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
