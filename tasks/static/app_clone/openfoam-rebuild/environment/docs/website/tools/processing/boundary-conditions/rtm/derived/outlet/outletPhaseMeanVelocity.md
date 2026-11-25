<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/outletPhaseMeanVelocity -->

# outletPhaseMeanVelocity

## Description

The `outletPhaseMeanVelocity` is a velocity\-outlet boundary condition that
adjusts the velocity for the given phase to achieve the specified mean thus
causing the phase\-fraction to adjust according to the mass flow rate.

Typical usage is as the outlet condition for a towing\-tank ship simulation
to maintain the outlet water level at the level as the inlet.

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
    type            outletPhaseMeanVelocity;
    Umean           <scalar>;
    alpha           <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `outletPhaseMeanVelocity` | word | yes | \- |
| `Umean` | Mean velocity normal to the boundary | scalar | yes | \- |
| `rho` | Name of phase\-fraction field | word | yes | \- |

The inherited entries are elaborated in:

* [Foam::mixedFvPatchField](https://api.openfoam.com/2606/Foam_mixedFvPatchField.html)

## Further information

Tutorial:

* [DTCHull](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/DTCHull)

Source code:

* [outletPhaseMeanVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/outletPhaseMeanVelocity)

API:

* [Foam::outletPhaseMeanVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_outletPhaseMeanVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.3\.0](https://www.openfoam.com/news/main-news/openfoam-2.3.0)
