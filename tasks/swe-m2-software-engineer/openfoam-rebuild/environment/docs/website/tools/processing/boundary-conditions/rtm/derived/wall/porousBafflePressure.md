<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/porousBafflePressure -->

# porousBafflePressure

## Description

The `porousBafflePressure` is boundary condition that provides
a jump condition, using the `cyclic` condition as a base.

The porous baffle introduces a pressure jump defined by:

Δp\=−(DμU\+0\.5Iρ∣U∣2)L \\Delta p \= \-(D \\mu U \+ 0\.5 I \\rho \|U\|^2 )LΔp\=−(DμU\+0\.5Iρ∣U∣2)L
where:

| Property | Description |
| --- | --- |
| ppp | Pressure \[Pa] |
| ρ\\rhoρ | Density \[kg/m^3] |
| μ\\muμ | Laminar viscosity \[Pa s] |
| DDD | Darcy coefficient |
| III | Inertial coefficient |
| LLL | Porous media length in the flow direction |

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type            wall;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            porousBafflePressure;
    D               <Function1<scalar>>;
    I               <Function1<scalar>>;
    length          <scalar>;

    // Optional entries
    phi             <word>;
    rho             <word>;
    uniformJump     <bool>;

    // Inherited entries
    patchType       cyclic;
    jump            uniform 0;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `porousBafflePressure` | word | yes | \- |
| `D` | Darcy coefficient | Function1\<scalar\> | yes | \- |
| `I` | Inertial coefficient | Function1\<scalar\> | yes | \- |
| `length` | Porous media length in the flow direction | scalar | yes | \- |
| `uniformJump` | Flag to apply a uniform pressure drop on the patch based | bool | no | false |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `patchType` | Underlying patch type should be `cyclic` | word | yes | \- |
| `jump` | Jump value | scalarField | yes | \- |

The inherited entries are elaborated in:

* fixedJumpFvPatchField.H
* PatchFunction1\.H

## Further information

Tutorial:

* [damBreakPorousBaffle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/damBreakPorousBaffle)

Source code:

* [porousBafflePressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/porousBafflePressure)

API:

* [Foam::porousBafflePressureFvPatchField](https://api.openfoam.com/2606/Foam_porousBafflePressureFvPatchField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
