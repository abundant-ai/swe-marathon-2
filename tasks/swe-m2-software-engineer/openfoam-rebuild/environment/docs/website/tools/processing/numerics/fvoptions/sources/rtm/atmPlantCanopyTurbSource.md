<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmPlantCanopyTurbSource -->

# atmPlantCanopyTurbSource

## Properties

* The `atmPlantCanopyTurbSource` applies sources on either `epsilon` or
`omega` to incorporate effects of plant canopy for atmospheric boundary
layer modelling.
* The `atmPlantCanopyTurbSource` can be applied on `epsilon` or
`omega` based RAS turbulence models.
* The `atmPlantCanopyTurbSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to either of the below, if exist:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

Required fields:

`epsilon`/`omega`
: Dissipation rate OR Spec. dissipation rate \[m2^22/s3^33]/\[1/s]

`plantCd`
: Plant canopy drag coefficient \[\-]

`leafAreaDensity`
: Leaf area density \[1/m]

## Model equations

### Turbulent kinetic energy dissipation rate

The model expression for `epsilon`:

Sp−\=αρ(C1−C2)Ccanopyϵ S\_p \-\= \\alpha \\rho \\left( C\_1 \- C\_2 \\right) C\_{canopy} \\epsilonSp​−\=αρ(C1​−C2​)Ccanopy​ϵ
with ([65](../../../../../../references.md#sogachev_atm_2006), Eq. 42\):

Ccanopy\=12\.0CμCdLAD∣uo∣ C\_{canopy} \= 12\.0 \\sqrt{C\_\\mu} C\_d {LAD} \|\\u\_o\|Ccanopy​\=12\.0Cμ​​Cd​LAD∣uo​∣
### Specific dissipation rate

The model expression for `omega`:

Sp−\=αρ(γ−β)Ccanopyω S\_p \-\= \\alpha \\rho \\left( \\gamma \- \\beta \\right) C\_{canopy} \\omegaSp​−\=αρ(γ−β)Ccanopy​ω
Where:

SpS\_pSp​
: Source term without boundary conditions

C1C\_1C1​
: Model constant (epsilon\-based models) \[\-]

C2C\_2C2​
: Model constant (epsilon\-based models) \[\-]

CμC\_\\muCμ​
: Empirical model constant \[\-]

β\\betaβ
: Model constant (omega\-based models) \[\-]

γ\\gammaγ
: Model constant (omega\-based models) \[\-]

ϵ\\epsilonϵ
: Turbulent kinetic energy dissipation rate (Current iteration) \[m2/s3]

ω\\omegaω
: Specific dissipation rate (Current iteration) \[1/s]

CdC\_dCd​
: Plant canopy drag coefficient \[\-]

LAD{LAD}LAD
: Leaf area density \[1/m]

uo\\u\_ouo​
: Previous\-iteration velocity field \[m/s]

CcanopyC\_{canopy}Ccanopy​
: Plant canopy term

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmPlantCanopyTurbSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmPlantCanopyTurbSource;

    atmPlantCanopyTurbSourceCoeffs
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
| type | Type name: atmPlantCanopyTurbSource | word | yes | \- |
| rho | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmPlantCanopyTurbSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmPlantCanopyTurbSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
