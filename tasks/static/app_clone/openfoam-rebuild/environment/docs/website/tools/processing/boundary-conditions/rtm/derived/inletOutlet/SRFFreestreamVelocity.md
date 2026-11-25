<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/SRFFreestreamVelocity -->

# SRFFreestreamVelocity

## Description

The `SRFFreestreamVelocity` is a boundary condition that provides
freestream velocity condition to be used in conjunction with the single
rotating frame (SRF) model (see: `SRFModel` class).

Given the free stream velocity in the absolute frame, the condition
applies the appropriate rotation transformation in time and space to
determine the local velocity using:

up\=cos(θ)uInf\+sin(θ)(n×uInf)−up,srf \\u\_p \= cos(\\theta) \\u\_{Inf} \+ sin(\\theta) (n \\times \\u\_{Inf}) \- \\u\_{p,srf}up​\=cos(θ)uInf​\+sin(θ)(n×uInf​)−up,srf​
where:

| Property | Description |
| --- | --- |
| up\\u\_pup​ | Patch velocity \[m/s] |
| uInf\\u\_{Inf}uInf​ | Free stream velocity in the absolute frame \[m/s] |
| θ\\thetaθ | Swept angle \[rad] |
| nnn | Axis direction of the SRF |
| up,srf\\u\_{p,srf}up,srf​ | SRF velocity of the patch \[m/s] |

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
    type            SRFFreestreamVelocity;
    UInf            <vector>;

    // Optional entries
    relative        <bool>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `SRFFreestreamVelocity` | word | yes | \- |
| `UInf` | Velocity of the free stream in the absolute frame | vector | yes | \- |
| `relative` | Flag to decide if the supplied inlet value relative to the SRF | bool | no | false |

The inherited entries are elaborated in:

* inletOutletFvPatchFields.H

## Further information

Tutorial:

* [rotor2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/SRFPimpleFoam/rotor2D)

Source code:

* [SRFFreestreamVelocityFvPatchVectorField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/cfdTools/general/SRF/derivedFvPatchFields/SRFFreestreamVelocityFvPatchVectorField)

API:

* [Foam::SRFFreestreamVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_SRFFreestreamVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.0\.0](https://www.openfoam.com/news/main-news/openfoam-2.0.0)
