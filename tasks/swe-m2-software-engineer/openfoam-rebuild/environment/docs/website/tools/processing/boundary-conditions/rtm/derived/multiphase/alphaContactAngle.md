<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/alphaContactAngle -->

# alphaContactAngle

## Description

The `alphaContactAngle` is a boundary condition that provides
contact\-angle boundary condition for multi\-phase interface\-capturing
simulations. It is used in conjunction with `multiphaseSystem`.

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
    type                      alphaContactAngle;
    thetaProperties
    (
        (<phase1> <phase2>) <scalar1> <scalar2> <scalar3> <scalar4>
        (<phase3> <phase2>) <scalar1> <scalar2> <scalar3> <scalar4>
        ...
    );

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `alphaContactAngle` | word | yes | \- |
| `thetaProperties` | Contact\-angle properties | dict | yes | \- |
| \<scalar1\> | Equilibrium contact angle | scalar | yes | \- |
| \<scalar2\> | Dynamic contact angle velocity scale | scalar | yes | \- |
| \<scalar3\> | Limiting advancing contact angle | scalar | yes | \- |
| \<scalar4\> | Limiting receding contact angle | scalar | yes | \- |

The inherited entries are elaborated in:

* zeroGradientFvPatchFields.H

## Further information

Tutorial:

* [damBreak4phase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/multiphaseInterFoam/laminar/damBreak4phase)

Source code:

* [alphaContactAngle](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/reactingEuler/multiphaseSystem/derivedFvPatchFields/alphaContactAngle)

API:

* [Foam::reactingMultiphaseEuler::alphaContactAngleFvPatchScalarField](https://api.openfoam.com/2606/Foam_reactingMultiphaseEuler_alphaContactAngleFvPatchScalarField.html)

**History:** Introduced in version [v2012](https://www.openfoam.com/news/main-news/openfoam-v2012)
