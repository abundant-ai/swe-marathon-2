<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/SRFVelocity -->

# SRFVelocity

## Description

The `SRFVelocity` is a boundary condition that provides
a velocity condition to be used in conjunction with the single
rotating frame (SRF) model (see: `SRFModel` class).

Given the free stream velocity in the absolute frame, the condition
applies the appropriate rotation transformation in time and space to
determine the local velocity.

The optional `relative` flag switches the behaviour of the patch
such that:

* `relative` \= yes: inlet velocity applied 'as is':

up\=uin \\u\_p \= \\u\_{in}up​\=uin​
* `relative` \= no : SRF velocity is subtracted from the inlet velocity:

up\=uin−up,srf \\u\_p \= \\u\_{in} \- \\u\_{p,srf}up​\=uin​−up,srf​
where:

| Property | Description |
| --- | --- |
| up\\u\_pup​ | Patch velocity \[m/s] |
| uin\\u\_{in}uin​ | User\-specified inlet velocity |
| up,srf\\u\_{p,srf}up,srf​ | SRF velocity |

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
    type            SRFVelocity;
    inletValue      <vectorField>;
    relative        <bool>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `SRFVelocity` | word | yes | \- |
| `inletValue` | Inlet velocity | vectorField | yes | \- |
| `relative` | Flag to decide if the supplied inlet value relative to the SRF | bool | yes | \- |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [mixer](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/SRFSimpleFoam/mixer)

Source code:

* [SRFVelocityFvPatchVectorField](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/cfdTools/general/SRF/derivedFvPatchFields/SRFVelocityFvPatchVectorField)

API:

* [Foam::SRFVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_SRFVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
