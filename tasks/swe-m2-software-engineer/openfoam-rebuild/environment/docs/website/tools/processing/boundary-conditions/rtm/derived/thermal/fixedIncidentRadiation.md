<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/fixedIncidentRadiation -->

# fixedIncidentRadiation

## Description

The `fixedIncidentRadiation` is a boundary condition for
thermal coupling for solid regions. It is used to emulate a fixed incident
radiative heat flux on a wall.

The gradient heat flux is calculated as:

qr\=ϵ∗(qr,incident−σT4) q\_r \= \\epsilon\*(q\_{r, incident} \- \\sigma\_ T^4\)qr​\=ϵ∗(qr,incident​−σT4​)
where:

| Property | Description |
| --- | --- |
| ϵ\\epsilonϵ | Emissivity of the solid |
| qr,incidentq\_{r, incident}qr,incident​ | Specified fixed incident radiation |
| TTT | Temperature |

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
    type            fixedIncidentRadiation;
    qrIncident      <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fixedIncidentRadiation` | word | yes | \- |
| `qrIncident` | Incident radiative heat flux | scalarField | yes | \- |

The inherited entries are elaborated in:

* fixedGradientFvPatchField.H
* temperatureCoupledBase.H

## Further information

Tutorial:

* [simplePMMApanel](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/fireFoam/LES/simplePMMApanel)

Source code:

* [fixedIncidentRadiation](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/fixedIncidentRadiation)

API:

* [Foam::radiation::fixedIncidentRadiationFvPatchScalarField](https://api.openfoam.com/2606/Foam_radiation_fixedIncidentRadiationFvPatchScalarField.html)

**History:** Introduced in version [2206](https://www.openfoam.com/news/main-news/openfoam-2206)
