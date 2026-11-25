<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/coupled/fan -->

# fan

## Description

The `fan` is a general boundary condition to simulate a jump
condition between a pair of patches, using the `cyclic` condition as a base.
The condition can accept user\-defined fan curve of pressure rise vs velocity.

The non\-dimensional flux is calculated as follows:

ϕ\=120Unπ3dmrpm \\phi \= \\frac{120 U\_n}{\\pi^3 d\_m r\_{pm}}ϕ\=π3dm​rpm​120Un​​
The non\-dimensional pressure:

Ψ\=2ΔPρ(πωdm)2 \\Psi \= \\frac{2 \\Delta P}{\\rho (\\pi \\omega d\_m)^2}Ψ\=ρ(πωdm​)22ΔP​

| Property | Description |
| --- | --- |
| dmd\_mdm​ | Fan mean diameter |
| rpmr\_{pm}rpm​ | Fan rpm |
| ΔP\\Delta PΔP | Pressure drop |
| ω\\omegaω | Rotational speed \[rad/s] |

The non\-dimensional table should be given as Ψ\=F(ϕ)\\Psi \= F(\\phi)Ψ\=F(ϕ).

## Usage

The condition requires entries in both the `boundary` and field files.

### Boundary file

```
<patchName>
{
    type            cyclic;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type            fan;
    jumpTable       <Function1<Type>>;

    // Optional entries
    phi             <word>;
    rho             <word>;
    uniformJump     <bool>;
    nonDimensional  <bool>;

    // Conditional entries

      // if 'nonDimensional' is true
      rpm           <Function1<scalar>>;
      dm            <Function1<scalar>>;

    // Inherited entries
    patchType       cyclic;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fan` | word | yes | \- |
| `jumpTable` | Jump dataset | Function1\<Type\> | yes | \- |
| `phi` | Name of the flux transporting the field | word | no | phi |
| `rho` | Name of the density field for normalising the mass flux | word | no | rho |
| `uniformJump` | Flag to apply uniform pressure drop | bool | no | false |
| `nonDimensional` | Flag to use non\-dimensional curves | bool | no | false |
| `rpm` | Fan rpm (for non\-dimensional curve) | Function1\<scalar\> | conditional | \- |
| `dm` | Fan mean diameter (for non\-dimensional curve) | Function1\<scalar\> | conditional | \- |

The inherited entries are elaborated in:

* [Foam::uniformJumpFvPatchField](https://api.openfoam.com/2606/Foam_uniformJumpFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* The underlying `patchType` should be set to `cyclic`.

## Further information

Tutorial:

* [TJunctionFan](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/pimpleFoam/RAS/TJunctionFan)

Source code:

* [fan](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fan)

API:

* [Foam::fanFvPatchField](https://api.openfoam.com/2606/Foam_fanFvPatchField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
