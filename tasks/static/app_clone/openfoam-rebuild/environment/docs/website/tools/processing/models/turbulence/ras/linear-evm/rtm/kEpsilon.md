<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/kEpsilon -->

# k\-ε

## Properties

* Two transport\-equation linear\-eddy\-viscosity turbulence closure model:
	+ Turbulent kinetic energy, kkk,
	+ Turbulent kinetic energy dissipation rate, ϵ\\epsilonϵ.
* Based on:
	+ Standard model: *Launder and Spalding (1974\)* [36](../../../../../../../references.md#launder_numerical_1974),
	+ Rapid Distortion Theory compression term: *El Tahry (1983\)*
	[16](../../../../../../../references.md#el_tahry_k-epsilon_1983).
* Extensively used with known performance,
* Over\-prediction of turbulent kinetic energy at stagnation points,
* Requires near\-wall treatment.

## Model equations

The **turbulent kinetic energy** equation, kkk
[36](../../../../../../../references.md#launder_numerical_1974)]:

DDt(ρk)\=∇ ∙ (ρDk∇k)\+P−ρϵ \\Ddt{\\rho k}
 \=
 \\div \\left( \\rho D\_k \\grad k \\right)
 \+ P
 \- \\rho \\epsilonDtD​(ρk)\=∇∙(ρDk​∇k)\+P−ρϵ
Where:

kkk
: Turbulent kinetic energy \[m2s−2\\text{m}^2 \\text{s}^{\-2} m2s−2]

DkD\_kDk​
: Effective diffusivity for kkk \[\-]

PPP
: Turbulent kinetic energy production rate \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

ϵ\\epsilonϵ
: Turbulent kinetic energy dissipation rate \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

The **turbulent kinetic energy dissipation rate** equation,
ϵ\\epsilonϵ [36](../../../../../../../references.md#launder_numerical_1974)]:

DDt(ρϵ)\=∇ ∙ (ρDϵ∇ϵ)\+C1ϵk(P\+C323k∇ ∙ u)−C2ρϵ2k \\Ddt{\\rho \\epsilon}
 \=
 \\div \\left( \\rho D\_{\\epsilon} \\grad \\epsilon \\right)
 \+ \\frac{C\_1 \\epsilon}{k} \\left( P \+ C\_3 \\frac{2}{3} k \\div \\u \\right)
 \- C\_2 \\rho \\frac{\\epsilon^2}{k}DtD​(ρϵ)\=∇∙(ρDϵ​∇ϵ)\+kC1​ϵ​(P\+C3​32​k∇∙u)−C2​ρkϵ2​
Where:

DϵD\_\\epsilonDϵ​
: Effective diffusivity for ϵ\\epsilonϵ \[\-]

C1C\_1C1​
: Model coefficient \[\-]

C2C\_2C2​
: Model coefficient \[\-]

The **turbulent viscosity** equation, νt\\nu\_tνt​
[36](../../../../../../../references.md#launder_numerical_1974)]:

νt\=Cμk2ϵ \\nu\_t \= C\_{\\mu} \\frac{k^2}{\\epsilon}νt​\=Cμ​ϵk2​
Where:

CμC\_{\\mu}Cμ​
: Model coefficient for the turbulent viscosity \[\-]

νt\\nu\_tνt​
: Turbulent viscosity \[m2s−1\\text{m}^2 \\text{s}^{\-1}m2s−1]

## OpenFOAM implementation

### Equations

The **turbulent kinetic energy dissipation rate**, ϵ\\epsilonϵ:

∂∂t(αρϵ)\+∇ ∙ (αρuϵ)−∇2(αρDϵϵ)\=C1αρGϵk−((23C1−C3,RDT)αρ∇ ∙ uϵ)−(C2αρϵkϵ)\+Sϵ\+SfvOptions \\ddt{\\alpha \\rho \\epsilon}
 \+ \\div \\left( \\alpha \\rho \\u \\epsilon \\right)
 \- \\laplacian \\left( \\alpha \\rho D\_\\epsilon \\epsilon \\right)
 \=
 C\_1 \\alpha \\rho G \\frac{\\epsilon}{k}
 \- \\left(
 \\left( \\frac{2}{3} C\_1 \- C\_{3,RDT} \\right) \\alpha \\rho \\div \\u \\epsilon
 \\right)
 \- \\left(
 C\_2 \\alpha \\rho \\frac{\\epsilon}{k} \\epsilon
 \\right)
 \+ S\_\\epsilon
 \+ S\_{\\text{fvOptions}}∂t∂​(αρϵ)\+∇∙(αρuϵ)−∇2(αρDϵ​ϵ)\=C1​αρGkϵ​−((32​C1​−C3,RDT​)αρ∇∙uϵ)−(C2​αρkϵ​ϵ)\+Sϵ​\+SfvOptions​
Where:

α\\alphaα
: Phase fraction of the given phase \[\-]

ρ\\rhoρ
: Density of the fluid \[kgm−3\\text{kg} \\text{m}^{\-3}kgm−3]

GGG
: Turbulent kinetic energy production rate due to the anisotropic part of the Reynolds\-stress tensor \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

DϵD\_\\epsilonDϵ​
: Effective diffusivity for ϵ\\epsilonϵ \[\-]

C1C\_1C1​
: Model coefficient \[sss]

C2C\_2C2​
: Model coefficient \[\-]

C3,RDTC\_{3,RDT}C3,RDT​
: Rapid\-distortion theory compression term coefficient \[\-]

SϵS\_\\epsilonSϵ​
: Internal source term for ϵ\\epsilonϵ

SfvOptionsS\_{\\text{fvOptions}}SfvOptions​
: Source terms introduced by `fvOptions` dictionary for ϵ\\epsilonϵ

The **turbulent kinetic energy** equation, kkk:

∂∂t(αρk)\+∇ ∙ (αρuk)−∇2(αρDkk)\=αρG−(23αρ∇ ∙ uk)−(αρϵkk)\+Sk\+SfvOptions \\ddt{\\alpha \\rho k}
 \+ \\div \\left( \\alpha \\rho \\u k \\right)
 \- \\laplacian \\left( \\alpha \\rho D\_k k \\right)
 \=
 \\alpha \\rho G
 \- \\left( \\frac{2}{3} \\alpha \\rho \\div \\u k \\right)
 \- \\left( \\alpha \\rho \\frac{\\epsilon}{k} k \\right)
 \+ S\_k
 \+ S\_{\\text{fvOptions}}∂t∂​(αρk)\+∇∙(αρuk)−∇2(αρDk​k)\=αρG−(32​αρ∇∙uk)−(αρkϵ​k)\+Sk​\+SfvOptions​
Where:

SkS\_kSk​
: Internal source term for kkk

SfvOptionsS\_{\\text{fvOptions}}SfvOptions​
: Source terms introduced by `fvOptions` dictionary for kkk

Note that:

* buoyancy contributions are *not* included,
* the coefficient C3C\_3C3​ is not the same as C3,RDTC\_{3,RDT}C3,RDT​.

## Default model coefficients

The model coefficients are [36](../../../../../../../references.md#launder_numerical_1974);[16](../../../../../../../references.md#el_tahry_k-epsilon_1983)]:

Cμ\=0\.09;C1\=1\.44;C2\=1\.92;C3,RDT\=0\.0;σk\=1\.0;σϵ\=1\.3 C\_\\mu \= 0\.09; \\quad C\_1 \= 1\.44; \\quad C\_2 \= 1\.92; \\quad C\_{3, RDT} \= 0\.0; \\quad \\sigma\_k \= 1\.0; \\quad \\sigma\_\\epsilon \= 1\.3Cμ​\=0\.09;C1​\=1\.44;C2​\=1\.92;C3,RDT​\=0\.0;σk​\=1\.0;σϵ​\=1\.3
## Initial conditions

For isotropic turbulence, the turbulent kinetic energy can be estimated by:

k\=32(I∣uref∣)2 k \= \\frac{3}{2} \\left( I \\mag{\\u\_{\\mathit{ref}}} \\right)^{2}k\=23​(I∣uref​∣)2
Where:

III
: Turbulence intensity \[%]

uref\\u\_{\\mathit{ref}}uref​
: A reference flow speed \[ms−1\\text{m} \\text{s}^{\-1}ms−1]

For isotropic turbulence, the turbulence dissipation rate can be estimated by:

ϵ\=Cμ0\.75k1\.5L \\epsilon \= \\frac{C\_{\\mu}^{0\.75}k^{1\.5}}{L}ϵ\=LCμ0\.75​k1\.5​
Where:

CμC\_{\\mu}Cμ​
: A model constant equal to 0\.09 by default \[\-]

LLL
: A reference length scale \[m\\text{m}m]

## Boundary conditions

Inlet:

* [fixedValue](../../../../../boundary-conditions/rtm/derived/general/fixedValue.md)
* turbulentMixingLengthDissipationRateInlet

Outlet:

* [Zero gradient](../../../../../boundary-conditions/rtm/derived/general/zeroGradient.md)
* [Constrained outlet](../../../../../boundary-conditions/rtm/derived/inletOutlet/inletOutlet.md)

Walls:

* kLowReWallFunction
* kqRWallFunction
* epsilonWallFunction

## Usage

The model can be enabled by using **constant/turbulenceProperties**
dictionary:

```
RAS
{
    // Mandatory entries
    RASModel        kEpsilon;

    // Optional entries
    turbulence      on;
    printCoeffs     on;

    // Optional model coefficients
    Cmu             0.09;
    C1              1.44;
    C2              1.92;
    C3              0.0;
    sigmak          1.0;
    sigmaEps        1.3;
}

```

## Further information

Source code:

* [Foam::RASModels::kEpsilon](https://api.openfoam.com/2606/Foam_RASModels_kEpsilon.html)

References:

* Standard model: *Launder and Spalding (1974\)* [36](../../../../../../../references.md#launder_numerical_1974)
* Rapid Distortion Theory compression term: *El Tahry (1983\)*
[16](../../../../../../../references.md#el_tahry_k-epsilon_1983)
