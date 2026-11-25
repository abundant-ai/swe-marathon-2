<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/fluxCorrectedVelocity -->

# fluxCorrectedVelocity

## Description

The `fluxCorrectedVelocity` is a velocity\-outlet boundary condition that
corrects the extrapolated velocity to match the specified flow rate.

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
    type            fluxCorrectedVelocity;

    // Optional entries
    phi             <word>;
    rho             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fluxCorrectedVelocity` | word | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |

The inherited entries are elaborated in:

* [Foam::fvPatchField](https://api.openfoam.com/2606/Foam_fvPatchField.html)
* [Foam::zeroGradientFvPatchField](https://api.openfoam.com/2606/Foam_zeroGradientFvPatchField.html)

## Method

up\=uc−n(n⋅uc)\+nϕp∣Sf∣ \\mathbf{u}\_p \=
 \\mathbf{u}\_c
\- \\mathbf{n} (\\mathbf{n} \\cdot \\mathbf{u}\_c)
\+ \\frac{\\mathbf{n} \\phi\_p}{\|\\mathbf{S}\_f\|}up​\=uc​−n(n⋅uc​)\+∣Sf​∣nϕp​​
where:

| Property | Description |
| --- | --- |
| up\\mathbf{u}\_pup​ | Patch velocity \[m/s] |
| uc\\mathbf{u}\_cuc​ | Velocity in cells adjacent to the patch \[m/s] |
| uc\\mathbf{u}\_cuc​ | Patch\-normal vectors \[\-] |
| ϕp\\phi\_pϕp​ | Patch flux \[m^3/s] or \[kg/s] |
| Sf\\mathbf{S}\_fSf​ | Patch face area vectors \[m^2] |

## Further information

Tutorial:

* [damBreak4phase](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/multiphaseEulerFoam/damBreak4phase)

Source code:

* [fluxCorrectedVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fluxCorrectedVelocity)

API:

* [Foam::fluxCorrectedVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_fluxCorrectedVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
