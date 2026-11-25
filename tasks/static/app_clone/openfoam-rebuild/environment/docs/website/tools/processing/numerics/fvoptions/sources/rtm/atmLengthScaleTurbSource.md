<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmLengthScaleTurbSource -->

# atmLengthScaleTurbSource

## Properties

* The `atmLengthScaleTurbSource` applies sources on either
`epsilon` or `omega` to correct mixing\-length scale estimations
for atmospheric boundary layer modelling.
* The `atmLengthScaleTurbSource` can be applied on `epsilon` or
`omega` based RAS turbulence models.
* The `atmLengthScaleTurbSource` inherits the traits of the
[fvOption](../../../../../../fundamentals/case-structure/fvoptions.md), and `cellSetOption`.

Corrections applied to either of the below, if exist:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

Required fields, either of the below:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

## Model equations

### Turbulent kinetic energy dissipation rate

The model expression for `epsilon`:

Sp\=αρC1∗GoνCμko S\_p \= \\alpha \\rho C\_1^\* \\frac{G\_o}{\\nu} C\_\\mu k\_oSp​\=αρC1∗​νGo​​Cμ​ko​
with ([4](../../../../../../references.md#apsley_atm_1997), Eq. 16 wherein the
exponentiation `n` is not present. `n` is an ad\-hoc implementation):

C1∗\=(C2−C1)(LLmax)n C\_1^\* \= (C\_2 \- C\_1\) \\left( \\frac{L}{L\_{max}} \\right)^nC1∗​\=(C2​−C1​)(Lmax​L​)n
Mixing\-length scale estimation ([59](../../../../../../references.md#pope_atm_2000), Eq. 10\.37 \& p. 374\):

L\=Cμ3/4ko3/2ϵo L \= C\_\\mu^{3/4} \\frac{k\_o^{3/2}}{\\epsilon\_o}L\=Cμ3/4​ϵo​ko3/2​​
### Specific dissipation rate

The model expression for `omega`:

Sp\=αργ∗Goν S\_p \= \\alpha \\rho \\gamma^\* \\frac{G\_o}{\\nu}Sp​\=αργ∗νGo​​
with ([33](../../../../../../references.md#langner_atm_2016), Eq. 3\.34\):

γ∗\=(γ−β)(LLmax)n \\gamma^\* \= \\left( \\gamma \- \\beta \\right) \\left( \\frac{L}{L\_{max}} \\right)^nγ∗\=(γ−β)(Lmax​L​)n
Mixing\-length scale estimation ([33](../../../../../../references.md#langner_atm_2016), Eq. 3\.20\):

L\=kCμ1/4ωo L \= \\frac{\\sqrt{k}}{C\_\\mu^{1/4} \\omega\_o}L\=Cμ1/4​ωo​k​​
Where:

SpS\_pSp​
: Source term without boundary conditions

ϵo\\epsilon\_oϵo​
: Previous\-iteration epsilon \[m2/s3]

ωo\\omega\_oωo​
: Previous\-iteration omega \[1/s]

kok\_oko​
: Previous\-iteration k \[m2/s2]

GoG\_oGo​
: Previous\-iteration k\-production contribution \[m2/s3]

C1C\_1C1​
: Model constant (epsilon\-based models) \[\-]

C2C\_2C2​
: Model constant (epsilon\-based models) \[\-]

C1∗C\_1^\*C1∗​
: Modified model constant field (epsilon\-based models) \[\-]

CμC\_\\muCμ​
: Empirical model constant \[\-]

γ\\gammaγ
: Model constant (omega\-based models) \[\-]

β\\betaβ
: Model constant (omega\-based models) \[\-]

γ∗\\gamma^\*γ∗
: Modified model constant field (omega\-based models) \[\-]

ν\\nuν
: Kinematic viscosity of fluid \[m2/s]

LLL
: Mixing\-length scale \[m]

LmaxL\_{max}Lmax​
: Maximum mixing\-length scale \[m]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmLengthScaleTurbSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmLengthScaleTurbSource;

    atmLengthScaleTurbSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Optional entries (unmodifiable)
        rho              rho;
        Lmax             41.575;
        n                3.0;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmLengthScaleTurbSource | word | yes | \- |
| rho | Name of density field | word | no | rho |
| Lmax | Maximum mixing\-length scale | scalar | no | 41\.575 |
| n | Mixing\-length scale exponent | scalar | no | 3\.0 |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmLengthScaleTurbSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmLengthScaleTurbSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
