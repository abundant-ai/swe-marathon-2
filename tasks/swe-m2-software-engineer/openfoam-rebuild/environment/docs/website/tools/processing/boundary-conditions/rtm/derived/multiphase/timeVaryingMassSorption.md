<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/multiphase/timeVaryingMassSorption -->

# timeVaryingMassSorption

## Description

The `timeVaryingMassSorption` is a boundary condition that provides
a first order fixed\-value condition for a given scalar field to model
time\-dependent adsorption\-desoprtion processes to be used with the
`interfaceOxideRate` mass model

dcdt\=kabsw(cint−cpw)\+kdes(cpw−cint) \\frac{d c}{d t} \=
 k\_{abs} w (c\_{int} \- c\_{p\_{w}}) \+ k\_{des} (c\_{p\_{w}} \- c\_{int})dtdc​\=kabs​w(cint​−cpw​​)\+kdes​(cpw​​−cint​)
w\=max⁡(1−cpw/max,0) w \= \\max(1 \- c\_{p\_{w}}/max, 0\)w\=max(1−cpw​​/max,0)
where:

| Property | Description |
| --- | --- |
| cintc\_{int}cint​ | Concentration at cell |
| cpwc\_{p\_{w}}cpw​​ | Concentration at wall |
| kabsk\_{abs}kabs​ | Adsorption rate constant \[1/s] |
| kdesk\_{des}kdes​ | Desorption rate constant \[1/s] |
| www | Weight function |
| maxmaxmax | Max concentration at wall |

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
    type        timeVaryingMassSorption;
    kbas        <scalar>;
    max         <scalar>;

    // Optional entries
    kdes        <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `timeVaryingAdsorption` | word | yes | \- |
| `kbas` | Adsorption rate constant | scalar | yes | \- |
| `max` | Maximum concentation at wall | scalar | yes | \- |
| `kdes` | Desorption rate constant | scalar | no | 0 |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Further information

Tutorial:

* [oxideFormation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/icoReactingMultiphaseInterFoam/oxideFormation)

Source code:

* [timeVaryingMassSorption](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/phaseSystemModels/multiphaseInter/phasesSystem/derivedFvPatchFields/timeVaryingMassSorption)

API:

* [Foam::timeVaryingMassSorptionFvPatchScalarField](https://api.openfoam.com/2606/Foam_timeVaryingMassSorptionFvPatchScalarField.html)

**History:** Introduced in version [v2106](https://www.openfoam.com/news/main-news/openfoam-v2106)
