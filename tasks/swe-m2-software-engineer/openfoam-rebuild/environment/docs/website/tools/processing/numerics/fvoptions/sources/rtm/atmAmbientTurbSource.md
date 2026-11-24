<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmAmbientTurbSource -->

# atmAmbientTurbSource

## Properties

* The `atmAmbientTurbSource` applies sources on `k` and either `epsilon`
or `omega` to prevent them dropping below a specified ambient value for
atmospheric boundary layer modelling.
* Such adjustment reportedly increases numerical stability for very stable
atmospheric stability conditions, and prevents nonphysical oscillations in
regions of low shear at higher altitudes.
* The `atmAmbientTurbSource` can be applied on `epsilon` or
`omega` based RAS turbulence models.
* The `atmAmbientTurbSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to:

`k`
: Turbulent kinetic energy \[m2^22/s2^22]

Corrections applied to either of the below, if exist:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

Required fields:

`k`
: Turbulent kinetic energy \[m2^22/s2^22]

and either of:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

## Model equations

The model expression for `epsilon` (Heuristically derived from
[60](../../../../../../references.md#rumsey_atm_2009), Eq. 4, rhs\-term:5\):

Sp\=αρC2ϵamb2kambϵoϵ S\_p \= \\alpha \\rho C\_2 \\frac{\\epsilon\_{amb}^2}{k\_{amb} \\epsilon\_o} \\epsilonSp​\=αρC2​kamb​ϵo​ϵamb2​​ϵ
The model expression for `omega` ([60](../../../../../../references.md#rumsey_atm_2009), Eq. 4, rhs\-term:5\):

Sp\=αρCμβωamb2ωoω S\_p \= \\alpha \\rho C\_\\mu \\beta \\frac{\\omega^2\_{amb}}{\\omega\_o} \\omegaSp​\=αρCμ​βωo​ωamb2​​ω
The model expression for `k` when `epsilon` is available
(Heuristically derived from ([60](../../../../../../references.md#rumsey_atm_2009), Eq. 3, rhs\-term:4\):

Sp\=αρϵambkok S\_p \= \\alpha \\rho \\frac{\\epsilon\_{amb}}{k\_o} kSp​\=αρko​ϵamb​​k
The model expression for `k` when `omega` is available
([60](../../../../../../references.md#rumsey_atm_2009), Eq. 3, rhs\-term:4\):

Sp\=αρCμωambkambkok S\_p \= \\alpha \\rho C\_\\mu \\frac{\\omega\_{amb} k\_{amb}}{k\_o} kSp​\=αρCμ​ko​ωamb​kamb​​k
Where:

SpS\_pSp​
: Source term without boundary conditions

ϵ\\epsilonϵ
: Turbulent kinetic energy dissipation rate (Current iteration) \[m2/s3]

ω\\omegaω
: Specific dissipation rate (Current iteration) \[1/s]

kkk
: Turbulent kinetic energy (Current iteration) \[m2/s2]

ϵamb\\epsilon\_{amb}ϵamb​
: Ambient epsilon value \[m2/s3]

ωamb\\omega\_{amb}ωamb​
: Ambient omega value \[1/s]

kambk\_{amb}kamb​
: Ambient k value \[m2/s2]

ϵo\\epsilon\_oϵo​
: Previous\-iteration epsilon \[m2/s3]

ωo\\omega\_oωo​
: Previous\-iteration omega \[1/s]

kok\_oko​
: Previous\-iteration k \[m2/s2]

C2C\_2C2​
: Model constant \[\-]

CμC\_\\muCμ​
: Empirical model constant \[\-]

β\\betaβ
: Model constant \[\-]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmAmbientTurbSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmAmbientTurbSource;

    atmAmbientTurbSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Mandatory entries (unmodifiable)
        kAmb              0.0;

        // Optional entries (unmodifiable)
        rho               rho;
        epsilonAmb        0.0;
        omegaAmb          0.0;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmAmbientTurbSource | word | yes | \- |
| kAmb | Ambient value for k | scalar | yes | \- |
| rho | Name of density field | word | no | rho |
| epsilonAmb | Ambient value for `epsilon` | scalar | no | 0\.0 |
| omegaAmb | Ambient value for `omega` | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmAmbientTurbSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmAmbientTurbSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
