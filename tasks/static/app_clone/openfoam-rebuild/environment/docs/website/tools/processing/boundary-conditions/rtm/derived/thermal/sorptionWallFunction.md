<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/sorptionWallFunction -->

# sorptionWallFunction

## Description

The `sorptionWallFunction` is a boundary condition that provides
a wall boundary condition to specify scalar/concentration gradient for
turbulent and laminar flows.

The governing equation of the boundary condition is:

∇C\=C∗−CpΔy\=FaΔy \\nabla C \= \\frac{C^\* \- C\_p}{\\Delta\_y} \= \\frac{F}{a \\Delta\_y}∇C\=Δy​C∗−Cp​​\=aΔy​F​
with:

C∗\=CsurfK C^\* \= \\frac{C\_{surf}}{K}C∗\=KCsurf​​
and with the mass\-transfer coefficient is calculated for turbulent flows:

a\=Cμ0\.25kp0\.5yblended\+ a \= \\frac{C\_\\mu^{0\.25} k\_p^{0\.5}}{y^\+\_{blended}}a\=yblended\+​Cμ0\.25​kp0\.5​​
or for laminar\-flow and molecular\-diffusion\-only states:

a\=Dmy1 a \= \\frac{D\_m}{y\_1}a\=y1​Dm​​
where:

| Property | Description |
| --- | --- |
| ∇C\\nabla C∇C | Gradient of concentration |
| C∗C^\*C∗ | Wall\-adjacent concentration |
| CpC\_pCp​ | Near\-wall cell concentration |
| Δy\\Delta\_yΔy​ | First\-cell centre wall distance |
| FFF | Flux of concentration |
| aaa | Mass\-transfer coefficient |
| CsurfC\_{surf}Csurf​ | Wall\-surface concentration |
| KKK | Adsorption or absorption/permeation coefficient |
| CμC\_\\muCμ​ | Empirical model coefficient |
| kpk\_pkp​ | Turbulent kinetic energy in near\-wall cell |
| yblended\+y^\+\_{blended}yblended\+​ | Non\-dimensional blended near\-wall cell height |
| DmD\_mDm​ | Molecular\-diffusion coefficient |
| y1y\_1y1​ | First\-cell centre wall distance |

#### References

Standard model for exponential blending (tag:FDC):

```
Foat, T., Drodge, J., Charleson, A., Whatmore, B.,
Pownall, S., Glover, P., ... & Marr, A. (2022).
Predicting vapour transport from semi-volatile organic
compounds concealed within permeable packaging.
International Journal of Heat and Mass Transfer, 183, 122012.
DOI:10.1016/j.ijheatmasstransfer.2021.122012

```

Standard model for stepwise blending (tag:F):

```
Foat, T. (2021).
Modelling vapour transport in indoor environments for
improved detection of explosives using dogs.
Doctoral dissertation. University of Southampton.
URI:http://eprints.soton.ac.uk/id/eprint/456709

```

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            compressible::sorptionWallFunction;
    Sc              <scalar>;
    Sct             <scalar>;
    kAbs            <PatchFunction1<scalar>>;

    // Optional entries
    laminar         <bool>;
    D               <scalar>;
    kName           <word>;
    nuName          <word>;

    // Inherited entries
    Cmu             <scalar>;
    kappa           <scalar>;
    E               <scalar>;
    blending        <word>;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `compressible::sorptionWallFunction` | word | yes | \- |
| `Sc` | Schmidt number | scalar | yes | \- |
| `Sct` | Turbulent Schmidt number | scalar | yes | \- |
| `kAbs` | Adsorption or absorption/permeation coefficient | PatchFunction1\<scalar\> | yes | \- |
| `laminar` | Flag to calculate mass\-transfer coefficient under the laminar\-flow or \-diffusion\-only states | bool | no | false |
| `kName` | Name of operand turbulent kinetic energy field | word | no | k |
| `nuName` | Name of operand kinematic viscosity field | word | no | nu |

The inherited entries are elaborated in:

* fixedGradientFvPatchField.H
* wallFunctionCoefficients.H
* wallFunctionBlenders.H
* PatchFunction1\.H

## Further information

Tutorial:

* N/A

Source code:

* [sorptionWallFunction](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/wallFunctions/sorptionWallFunction)

API:

* [Foam::sorptionWallFunctionFvPatchScalarField](https://api.openfoam.com/2606/Foam_sorptionWallFunctionFvPatchScalarField.html)

**History:** Introduced in version [v2212](https://www.openfoam.com/news/main-news/openfoam-v2212)
