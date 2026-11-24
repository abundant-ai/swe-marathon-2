<!-- https://doc.openfoam.com/2606/tools/processing/models/turbulence/ras/linear-evm/rtm/kOmegaSST -->

# k\-ω Shear Stress Transport (SST)

## Properties

* Two equation model for the turbulence kinetic energy, kkk, and
turbulence specific dissipation rate, ω\\omegaω.
* Aims to overcome the defficiencies of the standard k\-omega model wrt
dependency on the freestream values of k and omega
* Able to capture flow separation
* OpenFOAM variant is based on the 2003 model [49](../../../../../../../references.md#menter_ten_2003)

## Model equations

The turbulence specific dissipation rate equation is given by:

DDt(ρω)\=∇ ∙ (ρDω∇ω)\+ργGν−23ργω(∇ ∙ u)−ρβω2−ρ(F1−1)CDkω\+Sω, \\Ddt{\\rho \\omega}
 \=
 \\div \\left( \\rho D\_\\omega \\grad \\omega \\right)
 \+ \\frac{\\rho \\gamma G}{\\nu}
 \- \\frac{2}{3} \\rho \\gamma \\omega \\left( \\div \\u \\right)
 \- \\rho \\beta \\omega^2
 \- \\rho \\left(F\_1 \- 1\\right) CD\_{k\\omega}
 \+ S\_\\omega,DtD​(ρω)\=∇∙(ρDω​∇ω)\+νργG​−32​ργω(∇∙u)−ρβω2−ρ(F1​−1)CDkω​\+Sω​,
and the turbulence kinetic energy by:

DDt(ρk)\=∇ ∙ (ρDk∇k)\+ρG−23ρk(∇ ∙ u)−ρβ∗ωk\+Sk. \\Ddt{\\rho k}
 \=
 \\div \\left( \\rho D\_k \\grad k \\right)
 \+ \\rho G
 \- \\frac{2}{3} \\rho k \\left( \\div \\u \\right)
 \- \\rho \\beta^{\*} \\omega k
 \+ S\_k.DtD​(ρk)\=∇∙(ρDk​∇k)\+ρG−32​ρk(∇∙u)−ρβ∗ωk\+Sk​.
The turbulence viscosity is obtained using:

νt\=a1kmax⁡(a1ω,b1F23S) \\nu\_t \= a\_1 \\frac{k}{\\max (a\_1 \\omega\_, b\_1 F\_{23} \\tensor{S})}νt​\=a1​max(a1​ω,​b1​F23​S)k​
## Default model coefficients

| αk1\\alpha\_{k1}αk1​ | αk2\\alpha\_{k2}αk2​ | αω1\\alpha\_{\\omega 1}αω1​ | αω2\\alpha\_{\\omega 2}αω2​ | β1\\beta\_1β1​ | β2\\beta\_2β2​ | γ1\\gamma\_1γ1​ | γ2\\gamma\_2γ2​ |
| --- | --- | --- | --- | --- | --- | --- | --- |

```
0.85 |      1.0 |      0.5 |      0.856      |      0.075        |     0.0828  | 5/9 | 0.44

```

| β∗\\beta^{\*}β∗ | a1a\_1a1​ | b1b\_1b1​ | c1c\_1c1​ |
| --- | --- | --- | --- |

```
0.09 |      0.31 |       1.0 |     10.0

```

## Initialisation

For isotropic turbulence, the turbulence kinetic energy can be estimated by:

k\=32(I∣uref∣)2 k \= \\frac{3}{2} \\left(I \|\\u\_{\\ref}\|\\right)^{2}k\=23​(I∣uref​∣)2
where III is the intensity, and uref\\u\_{\\ref}uref​ a reference velocity.
The turbulence specific dissipation rate follows as:

ω\=k0\.5Cμ0\.25L \\omega \= \\frac{k^{0\.5}}{C\_{\\mu}^{0\.25} L}ω\=Cμ0\.25​Lk0\.5​
where CμC\_{\\mu}Cμ​ is a constant equal to 0\.09, and LLL a reference
length scale.

## Usage

The model is specified using:

```
RAS
{
    turbulence      on;
    RASModel        kOmegaSST;
}

```

## Boundary conditions

Inlet

* [fixedValue](../../../../../boundary-conditions/rtm/derived/general/fixedValue.md)
* [turbulentMixingLengthFrequencyInlet](https://api.openfoam.com/2606/Foam_turbulentMixingLengthDissipationRateInletFvPatchScalarField.html)

Outlet

* [Constrained outlet](../../../../../boundary-conditions/rtm/derived/inletOutlet/inletOutlet.md)

Walls

* wall functions

## Further information

Source code:

* [Foam::RASModels::kOmegaSST](https://api.openfoam.com/2606/Foam_RASModels_kOmegaSST.html)
* [Foam::kOmegaSSTBase](https://api.openfoam.com/2606/Foam_kOmegaSSTBase.html)

References:

* Base model: *Menter and Esch* [48](../../../../../../../references.md#menter_elements_2001)
* Updated model: *Menter et al.* [49](../../../../../../../references.md#menter_ten_2003)
* Corrections: consistent production terms from the 2001 paper as form in the
2003 paper is a typo, see [52](../../../../../../../references.md#nasa_langley_research_center_menter_2015)
* F3 term for rough walls: *Hellsten* [24](../../../../../../../references.md#hellsten_improvements_1997)

See also:

* [DES variant](../../../des/rtm/kOmegaSSTDES.md)
