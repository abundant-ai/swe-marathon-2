<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/turbulentMixingLengthFrequencyInlet -->

# turbulentMixingLengthFrequencyInlet

## Description

The `turbulentMixingLengthFrequencyInlet` is a boundary condition that
provides a turbulence specific dissipation, `omega` inlet condition based on
a specified mixing length. The patch values are calculated using:

ωp\=k0\.5Cμ0\.25L \\omega\_p \= \\frac{k^{0\.5}}{C\_{\\mu}^{0\.25} L}ωp​\=Cμ0\.25​Lk0\.5​
where:

| Property | Description |
| --- | --- |
| ωp\\omega\_pωp​ | Patch omega values \[1/s] |
| CμC\_\\muCμ​ | Empirical model constant retrived from turbulence model |
| kkk | Turbulent kinetic energy \[m^2/s^2] |
| LLL | Mixing length scale \[m] |

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
    type            turbulentMixingLengthFrequencyInlet;
    mixingLength    <scalar>;

    // Optional entries
    k               <word>;
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentMixingLengthFrequencyInlet` | word | yes | \- |
| `mixingLength` | Mixing length scale \[m] | scalar | yes | \- |
| `phi` | Name of flux field | word | no | phi |
| `k` | Name of turbulent kinetic energy field | word | no | k |

The inherited entries are elaborated in:

* inletOutletFvPatchFields.H

* In the event of reverse flow, a zero\-gradient condition is applied.

## Further information

Tutorial:

* [verticalChannel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/lagrangian/simpleReactingParcelFoam/verticalChannel)

Source code:

* [turbulentMixingLengthFrequencyInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/RAS/derivedFvPatchFields/turbulentMixingLengthFrequencyInlet)

API:

* [Foam::turbulentMixingLengthFrequencyInletFvPatchScalarField](https://api.openfoam.com/2606/Foam_turbulentMixingLengthFrequencyInletFvPatchScalarField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
