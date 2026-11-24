<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/kEpsilonPhitF -->

# k\-ε\-φ\-f

## Properties

* Three transport\-equation linear\-eddy\-viscosity RANS turbulence closure model
with an elliptic relaxation function:
	+ Turbulent kinetic energy, kkk,
	+ Turbulent kinetic energy dissipation rate, ϵ\\epsilonϵ,
	+ Normalised wall\-normal fluctuating velocity scale, ϕ\\phiϕ,

```
whose role is to predict *viscous damping*,

```

* Elliptic relaxation factor, fff, whose role is to predict effects of

```
pressure-rate-of-strain, i.e. to account for the non-local, wall-echo and
blocking effects of solid walls.

```

* Based on: *Laurence, Uribe, and Utyuzhnikov (2005\)*
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005)
* The name of the original variable replacing v2\\texttt{v2}v2 is
phi\\texttt{phi}phi in the original research paper
([38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 14\). However, the name
phi\\texttt{phi}phi preexisted in OpenFOAM; therefore, this name was replaced
by phit\\texttt{phit}phit.

## Model equations

The **turbulent kinetic energy** transport equation, kkk,
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 3]:

 \\partial\_t k
 \+ u\_i \\partial\_{x\_i} k
 \= P
 \- \\epsilon
 \+ \\partial\_{x\_j}
 \\left{
 \\left(
 \\nu \+ \\frac{\\nu\_t}{\\sigma\_k}
 \\right)
 \\partial\_{x\_j} k
 \\right}
Where:

kkk
: Turbulent kinetic energy \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

PPP
: Turbulent kinetic energy production rate \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

ϵ\\epsilonϵ
: Turbulent kinetic energy dissipation rate \[m2s−3\\text{m}^2 \\text{s}^{\-3}m2s−3]

ν\\nuν
: Kinematic viscosity of fluid \[m2s−1\\text{m}^2 \\text{s}^{\-1}m2s−1]

νt\\nu\_tνt​
: Turbulent viscosity \[m2s−1\\text{m}^2 \\text{s}^{\-1}m2s−1]

σk\\sigma\_kσk​
: Turbulent Prandtl number for kkk \[\-]

The **turbulent kinetic energy dissipation rate** transport equation,
ϵ\\epsilonϵ, [38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 4]:

 \\partial\_t \\epsilon
 \+ u\_i \\partial\_{x\_i} \\epsilon
 \=
 \\frac{C\_{\\epsilon\_1} P}{T}
 \- \\frac{C\_{\\epsilon\_2} \\epsilon}{T}
 \+ \\partial\_{x\_j}
 \\left{
 \\left(
 \\nu \+ \\frac{\\nu\_t}{\\sigma\_\\epsilon}
 \\right)
 \\partial\_{x\_j} \\epsilon
 \\right}
Where:

TTT
: Modelled turbulent time scale \[sss]

Cϵ∗C\_{\\epsilon\_\*}Cϵ∗​​
: Empirical model constants \[\-]

σϵ\\sigma\_\\epsilonσϵ​
: Turbulent Prandtl number for ϵ\\epsilonϵ \[\-]

The **normalised wall\-normal fluctuating velocity scale** transport equation,
ϕ\\phiϕ, [38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 17]:

 \\partial\_t \\phi
 \+ u\_i \\partial\_{x\_i} \\phi
 \=
 f
 \- P \\frac{\\phi}{k}
 \+ \\frac{2 \\nu\_t}{k \\sigma\_k} \\partial\_{x\_j} \\phi \\partial\_{x\_j} k
 \+
 \\partial\_{x\_j}
 \\left{
 \\left(
 \\frac{\\nu\_t}{\\sigma\_k}
 \\right)
 \\partial\_{x\_j} \\phi
 \\right}
where:

fff
: Elliptic relaxation factor \[s−1s^{\-1}s−1]

ϕ\\phiϕ
: Normalised wall\-normal fluctuating velocity scale \[\-]

σϕ\\sigma\_\\phiσϕ​
: Turbulent Prandtl number for ϕ\\phiϕ \[\-]

The **elliptic relaxation factor** equation, fff,
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 18]:

L2∂xj2f−f\=1T(C1−1)\[ϕ−23]−C2Pk−2νk∂xjϕ∂xjk−ν∂xj2ϕ L^2
 \\partial^2\_{x\_j} f
 \- f
 \=
 \\frac{1}{T}
 (C\_1 \- 1\)
 \\left\[
 \\phi \- \\frac{2}{3}
 \\right]
 \- C\_2 \\frac{P}{k}
 \- 2 \\frac{\\nu }{k} \\partial\_{x\_j} \\phi \\partial\_{x\_j} k
 \- \\nu \\partial^2\_{x\_j} \\phiL2∂xj​2​f−f\=T1​(C1​−1)\[ϕ−32​]−C2​kP​−2kν​∂xj​​ϕ∂xj​​k−ν∂xj​2​ϕ
Where:

LLL
: Modelled turbulent length scale \[mmm]

Cf∗C\_{f\_\*}Cf∗​​
: Empirical model constants \[\-]

The **turbulent time scale** equation, TTT,
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 7]:

T\=max⁡\[kϵ,6\.0νϵ] T
 \=
 \\max
 \\left\[
 \\frac{k}{\\epsilon},
 6\.0 \\sqrt{\\frac{\\nu}{\\epsilon}}
 \\right]T\=max\[ϵk​,6\.0ϵν​​]
The **turbulent length scale** equation, LLL,
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 7]:

L\=CLmax⁡\[k1\.5ϵ,Cη(ν3ϵ)0\.25] L
 \=
 C\_L
 \\max
 \\left\[
 \\frac{k^{1\.5}}{\\epsilon},
 C\_\\eta \\left( \\frac{\\nu^3}{\\epsilon} \\right)^{0\.25}
 \\right]L\=CL​max\[ϵk1\.5​,Cη​(ϵν3​)0\.25]
Where:

CLC\_LCL​
: Empirical model constant \[\-]

CηC\_\\etaCη​
: Empirical model constant \[\-]

The **turbulent viscosity** equation, νt\\nu\_tνt​,
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), p. 173]:

νt\=CμϕkT \\nu\_t
 \=
 C\_\\mu
 \\phi
 k
 Tνt​\=Cμ​ϕkT
Where:

CμC\_{\\mu}Cμ​
: Model coefficient for the turbulent viscosity \[\-]

νt\\nu\_tνt​
: Turbulent viscosity \[m2s−1\\text{m}^2 \\text{s}^{\-1}m2s−1]

## OpenFOAM implementation

### Equations

The main differences between the implemented and original governing equations
are as follows:

* Change of variables in the ϵ\\epsilonϵ\-equation:
k/T→ϵk/T \\rightarrow \\epsilonk/T→ϵ (when the term PPP was expanded into
its constituents),
* Change of variables in the kkk\-equation:
ϵ/k→1/T\\epsilon/k \\rightarrow 1/Tϵ/k→1/T,
* Inclusion of `nu` into `DphitEff` even though it is not present in
[38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eq. 17] (This change has provided higher
level of resemblance to benchmarks for the tests considered, particularly for
the peak skin friction, yet pressure\-related predictions were unaffected.
Users can switch off `nu` in `DphitEff` by using `includeNu` entry in
`kEpsilonPhitFCoeffs` as shown below in order to follow the reference paper
thereat. `includeNu` is left `true` by default.)
* The implementation is compressible and multiphase even though the derivation
of the models in the original research paper did not consider compressibility
or multiphase effects.

The implementation of the ϵ\\epsilonϵ transport equation:

 \\ddt{\\alpha \\rho \\epsilon}
 \+ \\div \\left(\\alpha \\rho \\u \\epsilon \\right)
 \- \\laplacian \\left(\\alpha \\rho D\_\\epsilon \\epsilon \\right)
 \=
 \\alpha \\rho C\_{\\epsilon\_1} \\frac{G}{T}
 \-
 \\left(
 \\left{ \\frac{2}{3} C\_{\\epsilon\_1} \\right}
 \\left{ \\alpha \\rho \\div \\u \\right}
 \\epsilon
 \\right)
 \-
 \\left(
 \\alpha \\rho \\frac{C\_{\\epsilon\_2}}{T} \\epsilon
 \\right)
 \+ S\_{\\text{fvOptions}}
Where:

α\\alphaα
: Phase fraction of the given phase \[\-]

ρ\\rhoρ
: Density of the fluid \[kgm−3\\text{kg} m^{\-3}kgm−3]

SfvOptionsS\_{\\text{fvOptions}}SfvOptions​
: Source terms introduced by *fvOptions* dictionary

The implementation of the kkk transport equation:

∂∂t(αρk)\+∇ ∙ (αρuk)−∇2(αρDkk)\=αρG−(\[23αρ∇ ∙ uk])−(αρTk)\+SfvOptions \\ddt{ \\alpha \\rho k }
 \+ \\div \\left( \\alpha \\rho \\u k \\right)
 \- \\laplacian \\left( \\alpha \\rho D\_k k \\right)
 \=
 \\alpha \\rho G
 \-
 \\left(
 \\left\[ \\frac{2}{3} \\alpha \\rho \\div \\u k \\right]
 \\right)
 \-
 \\left(
 \\frac{\\alpha \\rho}{T} k
 \\right)
 \+ S\_{\\text{fvOptions}}∂t∂​(αρk)\+∇∙(αρuk)−∇2(αρDk​k)\=αρG−(\[32​αρ∇∙uk])−(Tαρ​k)\+SfvOptions​
Where

GGG
: Anisotropic contribution part of the turbulent kinetic energy production rate, i.e. P\=G−2/3k∇ ∙ uP \= G \- 2/3 k \\div \\uP\=G−2/3k∇∙u

The implementation of the fff elliptic relaxation equation:

−∇2f\=−(1L2f)−((Cf1−1)ϕ−23T−Cf2Gk\+Cf223∇ ∙ u−2ν(∇ϕ⋅∇k)k−ν∇2ϕ)1L2 \- \\laplacian f
 \=
 \- \\left(
 \\frac{1}{L^2} f
 \\right)
 \- \\left(
 (C\_{f\_1} \- 1\) \\frac{\\phi \- \\frac{2}{3}}{T}
 \- \\frac{C\_{f\_2} G}{k}
 \+ C\_{f\_2} \\frac{2}{3} \\div \\u
 \- \\frac{2 \\nu (\\nabla \\phi \\cdot \\nabla k )}{k}
 \- \\nu \\laplacian \\phi
 \\right)\\frac{1}{L^2}−∇2f\=−(L21​f)−((Cf1​​−1)Tϕ−32​​−kCf2​​G​\+Cf2​​32​∇∙u−k2ν(∇ϕ⋅∇k)​−ν∇2ϕ)L21​
The implementation of the ϕ\\phiϕ transport equation:

 \\ddt{\\alpha \\rho \\phi}
 \+ \\div \\left(\\alpha \\rho \\u \\phi \\right)
 \- \\laplacian \\left(\\alpha \\rho D\_\\phi \\, \\phi \\right)
 \=
 \\alpha \\rho f
 \-
 \\left(
 \\alpha \\rho
 \\left{
 \\frac{G}{k}
 \- \\frac{2}{3} \\div \\u
 \- \\frac{2 \\nu (\\nabla \\phi \\cdot \\nabla k )}{k \\sigma\_k \\phi }
 \\right}
 \\phi
 \\right)
 \+ S\_{\\text{fvOptions}}
The implementation of the TTT equation:

T\=max⁡(kϵ,CTmax⁡ν,0ϵ) T
 \=
 \\max
 \\left(
 \\frac{k}{\\epsilon},
 C\_T \\frac{\\sqrt{\\max{\\nu, 0}}}{\\epsilon}
 \\right)T\=max(ϵk​,CT​ϵmaxν,0​​)
The implementation of the LLL equation:

L\=CLmax⁡(k1\.5ϵ,Cη\[(max⁡ν,0)3ϵ]0\.25) L
 \=
 C\_L
 \\max
 \\left(
 \\frac{k^{1\.5}}{\\epsilon},
 C\_\\eta
 \\left\[
 \\frac{(\\max{\\nu, 0})^3}{\\epsilon}
 \\right]^{0\.25}
 \\right)L\=CL​max(ϵk1\.5​,Cη​\[ϵ(maxν,0)3​]0\.25)
## Default model coefficients

The model coefficients are [38](../../../../../../../references.md#laurence_kepsilonphitf_2005), Eqs. 19\-20]:

Cμ\=0\.22;Cϵ1\=1\.4(1\.0\+0\.051\.0/ϕ);Cϵ2\=1\.9;CT\=6\.0;CL\=0\.25;Cf1\=1\.4;Cf2\=0\.3;Cη\=110\.0;σk\=1\.0;σϵ\=1\.3;σϕ\=1\.0\.\\begin{aligned}
 C\_\\mu \= 0\.22; \\quad C\_{\\epsilon\_1} \= 1\.4(1\.0 \+ 0\.05\\sqrt{1\.0/\\phi} ); \\quad C\_{\\epsilon\_2} \= 1\.9; \\quad C\_T \= 6\.0; \\quad C\_L \= 0\.25;\\\\
 C\_{f\_1} \= 1\.4; \\quad C\_{f\_2} \= 0\.3; \\quad C\_\\eta \= 110\.0; \\quad \\sigma\_k \= 1\.0; \\quad \\sigma\_\\epsilon \= 1\.3; \\quad \\sigma\_\\phi \= 1\.0\.
\\end{aligned}Cμ​\=0\.22;Cϵ1​​\=1\.4(1\.0\+0\.051\.0/ϕ​);Cϵ2​​\=1\.9;CT​\=6\.0;CL​\=0\.25;Cf1​​\=1\.4;Cf2​​\=0\.3;Cη​\=110\.0;σk​\=1\.0;σϵ​\=1\.3;σϕ​\=1\.0\.​
Please note that [38](../../../../../../../references.md#laurence_kepsilonphitf_2005), p. 176] stated that the
model constants above have been calibrated to match the flow statistics of
the smooth\-wall plane channel flow at Reτ\=395\\text{Re}\_\\tau \= 395Reτ​\=395.

## Usage

The model can be enabled by using **constant/turbulenceProperties**
dictionary:

```
simulationType    RAS;
RAS
{
  // Mandatory entries
  RASModel    kEpsilonPhitF;

  // Optional entries
  turbulence      on;
  printCoeffs     on;
  kEpsilonPhitFCoeffs
  {
      includeNu   true;    // include nu in DphitEff()
      Cmu         0.22;    // Turbulent viscosity constant
      Ceps1a      1.4;     // Model constant for epsilon
      Ceps1b      1.0;     // Model constant for epsilon
      Ceps1c      0.05;    // Model constant for epsilon
      Ceps2       1.9;     // Model constant for epsilon
      Cf1         1.4;     // Model constant for f
      Cf2         0.3;     // Model constant for f
      CL          0.25;    // Model constant for L
      Ceta        110.0;   // Model constant for L
      CT          6.0;     // Model constant for T
      sigmaK      1.0;     // Turbulent Prandtl number for k
      sigmaEps    1.3;     // Turbulent Prandtl number for epsilon
      sigmaPhit   1.0;     // Turbulent Prandtl number for phit = sigmaK
  }

```

Please note that ϕ\\phiϕ is a *symmetric*, and fff is an
*asymmetric* matrix.

### Initial conditions

For kkk and ϵ\\epsilonϵ fields, the initial conditions can be
estimated by using the recommendations made for the
[kEpsilon model](kEpsilon.md#initialisation).

For ϕ\\phiϕ:

```
object                phit;
dimensions            [0 0 0 0 0 0 0];
internalField         uniform 0.66;

```

For fff:

```
object                f;
dimensions            [0 0 -1 0 0 0 0];
internalField         uniform 1.0;

```

### Boundary conditions

For kkk and ϵ\\epsilonϵ fields, please use the boundary conditions
that are available for the
[kEpsilon model](kEpsilon.md#bcs).

For ϕ\\phiϕ and fff:

Inlet/Outlet:

* [Zero gradient](../../../../../boundary-conditions/rtm/derived/general/zeroGradient.md)

Walls:

* No wall function is required for ϕ\\phiϕ or fff fields,
* [fixedValue](../../../../../boundary-conditions/rtm/derived/general/fixedValue.md) with ϕ\\phiϕ and fff zero
at the wall can be used.

For example, ϕ\\phiϕ:

```
object          phit;
dimensions      [0 0 0 0 0 0 0];
wall
{
    type      fixedValue;
    value     uniform 1e-10;
}
"(inlet|outlet)"
{
    type      zeroGradient;
}

```

For example, fff:

```
object          f;
dimensions      [0 0 -1 0 0 0 0];
wall
{
    type      fixedValue;
    value     uniform 0;
}
"(inlet|outlet)"
{
    type      zeroGradient;
}

```

## Further information

Source code:

* [Foam::RASModels::kEpsilonPhitF](https://api.openfoam.com/2606/Foam_RASModels_kEpsilonPhitF.html)

References:

* : *Laurence, Uribe, and Utyuzhnikov (2005\)* [38](../../../../../../../references.md#laurence_kepsilonphitf_2005)
