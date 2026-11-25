<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmPlantCanopyUSource -->

# atmPlantCanopyUSource

## Properties

* The `atmPlantCanopyUSource` applies sources on velocity, i.e. `U`,
to incorporate effects of plant canopy for atmospheric boundary layer modelling.
* The `atmPlantCanopyUSource` can be applied on any RAS turbulence model.
* The `atmPlantCanopyUSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to:

`U`
: Velocity \[m/s]

Required fields:

`U`
: Velocity \[m/s]

`plantCd`
: Plant canopy drag coefficient \[\-]

`leafAreaDensity`
: Leaf area density \[1/m]

## Model equations

The model expression ([65](../../../../../../references.md#sogachev_atm_2006), Eq. 42\):

Sp−\=αρ(CdLAD∣uo∣)u S\_p \-\= \\alpha \\rho \\left( C\_d {LAD} \|\\u\_o\| \\right) \\uSp​−\=αρ(Cd​LAD∣uo​∣)u
where

fMf\_MfM​
: fvMatrix of the velocity field

CdC\_dCd​
: Plant canopy drag coefficient \[\-]

LAD{LAD}LAD
: Leaf area density \[1/m]

uo\\u\_ouo​
: Previous\-iteration velocity field \[m/s]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmPlantCanopyUSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmPlantCanopyUSource;

    atmPlantCanopyUSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Optional entries (unmodifiable)
        rho             rho;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmPlantCanopyUSource | word | yes | \- |
| rho | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmPlantCanopyUSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmPlantCanopyUSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
