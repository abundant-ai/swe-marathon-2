<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/swirlFanVelocity -->

# swirlFanVelocity

## Description

The `swirlFanVelocity` is a boundary condition that provides a jump condition
for velocity across a cyclic pressure jump condition and applies a
transformation to the velocity.

The velocity jump is specified with a swirl component as follows:

utan\=ΔPrefffeffωrpmπ30 u\_{tan} \= \\frac{\\Delta\_P}{r\_{eff} f\_{eff} \\omega\_{rpm} \\frac{\\pi}{30}}utan​\=reff​feff​ωrpm​30π​ΔP​​
where:

| Property | Description |
| --- | --- |
| utanu\_{tan}utan​ | Tangential component of velocity |
| ΔP\\Delta\_PΔP​ | Pressure drop across the cyclic |
| reffr\_{eff}reff​ | Effective radius |
| fefff\_{eff}feff​ | Fan efficiency coefficient |
| ωrpm\\omega\_{rpm}ωrpm​ | RPM of the fan |

Alternatively an inner and outer radii can be used instead of reffr\_{eff}reff​.
The utanu\_{tan}utan​ is as follows for r\>rinnerr \> r\_{inner}r\>rinner​ and r\<routerr \< r\_{outer}r\<router​:

utan\=ΔPrfeffωrpmπ30 u\_{tan} \= \\frac{\\Delta\_P}{r f\_{eff} \\frac{\\omega\_{rpm}}{\\pi 30}}utan​\=rfeff​π30ωrpm​​ΔP​​
with r\=xf−xoriginr \= x\_{f} \- x\_{origin}r\=xf​−xorigin​, and fff is the face center.

The radial velocity is zero in the this model.

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
    type            swirlFanVelocity;
    rpm             <Function1<scalar>>;

    // Optional entries
    phi             <word>;
    p               <word>;
    rho             <word>;
    origin          <vector>;
    fanEff          <scalar>;
    rEff            <scalar>;
    rInner          <scalar>;
    rOuter          <scalar>;
    useRealRadius   <bool>;

    // Inherited entries
    patchType       cyclic;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `swirlFanVelocity` | word | yes | \- |
| `rpm` | RPM of the fan | Function1\<scalar\> | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `p` | Name of pressure field | word | no | p |
| `rho` | Name of density field | word | no | rho |
| `origin` | Fan centre | vector | no | Zero |
| `fanEff` | Fan efficiency | scalar | no | 1 |
| `rEff` | Effective radius | scalar | no | 0 |
| `rInner` | Inner radius | scalar | no | 0 |
| `rOuter` | Outer radius | scalar | no | 0 |
| `useRealRadius` | Flag to use inner/outer radii | bool | no | false |

The inherited entries are elaborated in:

* [Foam::fixedJumpFvPatchField](https://api.openfoam.com/2606/Foam_fixedJumpFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* Negative `rpm` will reverse the input tangential direction.
* This boundary condition needs to be used with a pressure\-jump (e.g. fan)
condition with a non\-zero dp, otherwise no swirl will be applied (dp\=0\).
* Please ensure physical and complementary set\-ups for the pressure\-jump
and `swirlFanVelocity` boundary conditions.

## Further information

Tutorial:

* N/A

Source code:

* [swirlFanVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/swirlFanVelocity)

API:

* [Foam::swirlFanVelocityFvPatchField](https://api.openfoam.com/2606/Foam_swirlFanVelocityFvPatchField.html)

**History:** Introduced in version [v1806](https://www.openfoam.com/news/main-news/openfoam-v1806)
