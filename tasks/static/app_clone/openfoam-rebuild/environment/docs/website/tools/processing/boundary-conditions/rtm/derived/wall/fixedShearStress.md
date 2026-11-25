<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/wall/fixedShearStress -->

# fixedShearStress

## Description

The `fixedShearStress` is boundary condition that
sets a user\-defined shear stress constant and uniform across a given
patch by using the expression:

τ0\=−νeffdudn \\tau\_0 \= \-\\nu\_{eff} \\frac{d\\u}{dn}τ0​\=−νeff​dndu​
where:

| Property | Description |
| --- | --- |
| τ\\tauτ | Shear stress |
| u\\uu | Velocity |
| νeff\\nu\_{eff}νeff​ | Effective viscosity |
| nnn | Wall normal direction |

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
    type            fixedShearStress;

    // Optional entries
    tau             <vector>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedShearStress` | word | yes | \- |
| `tau` | Type name: `fixedShearStress` | vector | no | Zero |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [atmDownstreamDevelopment](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/verificationAndValidation/atmosphericModels/atmDownstreamDevelopment)

Source code:

* [fixedShearStress](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/derivedFvPatchFields/fixedShearStress)

API:

* [Foam::fixedShearStressFvPatchVectorField](https://api.openfoam.com/2606/Foam_fixedShearStressFvPatchVectorField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
