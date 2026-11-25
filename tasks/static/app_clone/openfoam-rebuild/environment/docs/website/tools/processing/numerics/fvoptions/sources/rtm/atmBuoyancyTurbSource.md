<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/sources/rtm/atmBuoyancyTurbSource -->

# atmBuoyancyTurbSource

## Properties

* The `atmBuoyancyTurbSource` applies sources on `k`
and either `epsilon` or `omega` to incorporate effects
of buoyancy for atmospheric boundary layer modelling.
* The `atmBuoyancyTurbSource` can be applied on `epsilon` or
`omega` based RAS turbulence models.
* The `atmBuoyancyTurbSource` inherits the traits of the
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

`alphat`
: Kinematic turbulent thermal conductivity \[m2^22/s]

and either of:

`epsilon`
: Turbulent kinetic energy dissipation rate \[m2^22/s3^33]

`omega`
: Specific dissipation rate \[1/s]

## Model equations

### Turbulent kinetic energy dissipation rate

The model expressions for `epsilon` ([2](../../../../../../references.md#alletto_atm_2018), Eq. 5, rhs\-term:3\):

Sp\=αρC3Bkoϵ S\_p \= \\alpha \\rho \\frac{C\_3 B}{k\_o} \\epsilonSp​\=αρko​C3​B​ϵ
with (([66](../../../../../../references.md#sogachev_atm_2012), Eq. 18, rhs\-term:3\),
([2](../../../../../../references.md#alletto_atm_2018), Eq. 5, rhs\-term:3 has a typo)):

C3\=(C1−C2)αB\+1\.0; C\_3 \= (C\_1 \- C\_2\) \\alpha\_B \+ 1\.0;C3​\=(C1​−C2​)αB​\+1\.0;
and ([2](../../../../../../references.md#alletto_atm_2018), Eq. 10, with a typo of C2C\_2C2​ instead of using (C2−1\.0)(C\_2 \- 1\.0\)(C2​−1\.0)):

αB\=neg0(R)(1\.0−(1\.0\+C2−1\.0C2−C1)L)\+pos(R)(1\.0−L) \\alpha\_B \= {neg}\_0 (R) (1\.0 \- (1\.0 \+ \\frac{C\_2 \- 1\.0}{C\_2 \- C\_1}) L )
 \+ pos(R) (1\.0 \- L)αB​\=neg0​(R)(1\.0−(1\.0\+C2​−C1​C2​−1\.0​)L)\+pos(R)(1\.0−L)
Mixing\-length scale estimation ([59](../../../../../../references.md#pope_atm_2000), Eq. 10\.37 \& p. 374\) normalised by LmaxL\_{max}Lmax​:

L\=Cμ3/4Lmaxko3/2ϵo L \= \\frac{C\_\\mu^{3/4}}{L\_{max}} \\frac{k\_o^{3/2}}{\\epsilon\_o}L\=Lmax​Cμ3/4​​ϵo​ko3/2​​
Gradient Richardson number ([2](../../../../../../references.md#alletto_atm_2018), Eq. 4\):

R\=−BGo\+ζ R \= \- \\frac{B}{G\_o \+ \\zeta}R\=−Go​\+ζB​
Buoyancy production term ([2](../../../../../../references.md#alletto_atm_2018), Eq. 7\):

B\=βBαto(∇To⋅g) B \= \\beta\_B \\alpha\_{t\_o} (\\grad{T\_o} \\cdot \\vec{g})B\=βB​αto​​(∇To​⋅g)
### Specific dissipation rate

The model expression for `omega` (([33](../../../../../../references.md#langner_atm_2016)) ([2](../../../../../../references.md#alletto_atm_2018), Eq. 5, rhs\-term:3\)):

Sp\=αρC3Bkoω S\_p \= \\alpha \\rho \\frac{C\_3 B}{k\_o} \\omegaSp​\=αρko​C3​B​ω
with (([66](../../../../../../references.md#sogachev_atm_2012), Eq. 19, rhs\-term:3\),
([2](../../../../../../references.md#alletto_atm_2018), Eq. 5, rhs\-term:3 has a typo)):

C3\=(γ−β)αB; C\_3 \= (\\gamma \- \\beta) \\alpha\_B;C3​\=(γ−β)αB​;
and ([2](../../../../../../references.md#alletto_atm_2018), Eq. 10\):

αB\=neg0(R)(1\.0−(1\.0\+ββ−γ)L)\+pos(R)(1\.0−L) \\alpha\_B \= {neg}\_0 (R) (1\.0 \- (1\.0 \+ \\frac{\\beta}{\\beta \- \\gamma}) L )
 \+ pos(R) (1\.0 \- L)αB​\=neg0​(R)(1\.0−(1\.0\+β−γβ​)L)\+pos(R)(1\.0−L)
Mixing\-length scale estimation ([33](../../../../../../references.md#langner_atm_2016) Eq. 3\.20\) normalised by LmaxL\_{max}Lmax​:

L\=1Cμ1/4Lmaxkoωo L \= \\frac{1}{C\_\\mu^{1/4} L\_{max}} \\frac{\\sqrt{k\_o}}{\\omega\_o}L\=Cμ1/4​Lmax​1​ωo​ko​​​
Gradient Richardson number ([2](../../../../../../references.md#alletto_atm_2018), Eq. 4\):

R\=−BGo\+ζ R \= \- \\frac{B}{G\_o \+ \\zeta}R\=−Go​\+ζB​
Buoyancy production term ([2](../../../../../../references.md#alletto_atm_2018), Eq. 7\):

B\=βBαto(∇To⋅g) B \= \\beta\_B \\alpha\_{t\_o} (\\grad{T\_o} \\cdot \\vec{g})B\=βB​αto​​(∇To​⋅g)
### Turbulent kinetic energy

The model expression for `k:`

Sp\=αρBkok S\_p \= \\alpha \\rho \\frac{B}{k\_o} kSp​\=αρko​B​k
Where:

SpS\_pSp​
: Source term without boundary conditions

ϵ\\epsilonϵ
: Turbulent kinetic energy dissipation rate (Current iteration) \[m2/s3]

ω\\omegaω
: Specific dissipation rate (Current iteration) \[1/s]

kkk
: Turbulent kinetic energy (Current iteration) \[m2/s2]

ϵo\\epsilon\_oϵo​
: Previous\-iteration epsilon \[m2/s3]

ωo\\omega\_oωo​
: Previous\-iteration omega \[1/s]

kok\_oko​
: Previous\-iteration k \[m2/s2]

C1C\_1C1​
: Model constant (epsilon\-based models) \[\-]

C2C\_2C2​
: Model constant (epsilon\-based models) \[\-]

β\\betaβ
: Model constant (omega\-based models) \[\-]

γ\\gammaγ
: Model constant (omega\-based models) \[\-]

C3C\_3C3​
: Modified model constant field \[\-]

LLL
: Normalised mixing\-length scale \[\-]

LmaxL\_{max}Lmax​
: Maximum mixing\-length scale \[m]

BBB
: Buoyancy production term \[m2/s3]

ToT\_oTo​
: Previous\-iteration temperature \[K]

αto\\alpha\_{t\_o}αto​​
: Previous\-iteration kinematic turbulent thermal conductivity \[m2/s]

GoG\_oGo​
: Previous\-iteration turbulent kinetic energy production contribution \[m2/s2]

g\\vec{g}g
: Gravitational field \[m/s2]

CμC\_\\muCμ​
: Empirical model constant \[\-]

RRR
: Gradient Richardson number \[\-]

βB\\beta\_BβB​
: Thermal expansion coefficient \[\-]

α\\alphaα
: Phase fraction in multiphase computations, otherwise equals to 1

ρ\\rhoρ
: Fluid density in compressible computations, otherwise equals to 1

ζ\\zetaζ
: Small value to prevent floating\-point exceptions \[\-]

## Usage

Example of the fvOptions specification using `constant/fvOptions` file:

```
atmBuoyancyTurbSource1
{
    // Mandatory entries (unmodifiable)
    type                  atmBuoyancyTurbSource;

    atmBuoyancyTurbSourceCoeffs
    {
        // Mandatory (inherited) entries (unmodifiable)
        selectionMode    all;

        // Optional (unmodifiable)
        rho          rho;
        Lmax         41.575;
        beta         3.3e-03;
    }

    // Optional (inherited) entries
    ...
}

```

where the entries mean:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| type | Type name: atmBuoyancyTurbSource | word | yes | \- |
| kAmb | Ambient value for `k` | scalar | yes | \- |
| rho | Name of density field | word | no | rho |
| Lmax | Maximum mixing\-length scale | scalar | no | 41\.575 |
| beta | Thermal expansion coefficient | scalar | no | 3\.3e\-03 |

The inherited entries are elaborated in:

* [fvOption](../../../../../../fundamentals/case-structure/fvoptions.md)
	+ `cellSetOption`

## Further information

Tutorials

* [atmFlatTerrain](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmFlatTerrain)
* [atmForestStability](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmForestStability)

Source code

* [atmBuoyancyTurbSource](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/atmosphericModels/fvOptions/atmBuoyancyTurbSource)

**History:** Introduced in version [v2006](https://www.openfoam.com/news/main-news/openfoam-v2006)
