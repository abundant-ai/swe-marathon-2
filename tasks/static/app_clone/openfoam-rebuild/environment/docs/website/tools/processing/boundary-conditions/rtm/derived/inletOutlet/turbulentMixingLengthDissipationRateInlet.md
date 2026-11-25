<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/turbulentMixingLengthDissipationRateInlet -->

# turbulentMixingLengthDissipationRateInlet

## Description

The `turbulentMixingLengthDissipationRateInlet` is a boundary condition that
calculates turbulent kinetic energy dissipation rate, i.e. `epsilon`,
based on a specified mixing length. The patch values are calculated using:

ϵp\=Cμ0\.75k1\.5L \\epsilon\_p \= \\frac{C\_{\\mu}^{0\.75} k^{1\.5}}{L}ϵp​\=LCμ0\.75​k1\.5​
where:

| Property | Description |
| --- | --- |
| ϵp\\epsilon\_pϵp​ | Patch epsilon values \[m^2/s^3] |
| CμC\_\\muCμ​ | Empirical model constant retrieved from turbulence model |
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
    type            turbulentMixingLengthDissipationRateInlet;
    mixingLength    <scalar>;

    // Optional entries
    Cmu             <scalar>;
    k               <word>;
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentMixingLengthDissipationRateInlet` | word | yes | \- |
| `mixingLength` | Mixing length scale \[m] | scalar | yes | \- |
| `Cmu` | Empirical model constant | scalar | no | 0\.09 |
| `phi` | Name of flux field | word | no | phi |
| `k` | Name of turbulent kinetic energy field | word | no | k |

The inherited entries are elaborated in:

* inletOutletFvPatchFields.H

* The boundary condition is derived from `inletOutlet` condition.
Therefore, in the event of reverse flow, a zero\-gradient condition
is applied.
* The order of precedence to input the empirical model constant `Cmu` is:
turbulence model, boundary condition dictionary, and default value\=0\.09\.
* The empirical model constant `Cmu` is not a spatiotemporal variant field.
Therefore, the use of the boundary condition may not be fully consistent
with the turbulence models where `Cmu` is a variant field, such as
`realizableKE` closure model in this respect. Nevertheless, workflow
observations suggest that the matter poses no importance.

## Further information

Tutorial:

* [TJunctionAverage](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/RAS/TJunctionAverage)

Source code:

* [turbulentMixingLengthDissipationRateInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/TurbulenceModels/turbulenceModels/RAS/derivedFvPatchFields/turbulentMixingLengthDissipationRateInlet)

API:

* [Foam::turbulentMixingLengthDissipationRateInletFvPatchScalarField](https://api.openfoam.com/2606/Foam_turbulentMixingLengthDissipationRateInletFvPatchScalarField.html)

**History:** Introduced in version [2\.2\.2](https://www.openfoam.com/news/main-news/openfoam-2.2.2)
