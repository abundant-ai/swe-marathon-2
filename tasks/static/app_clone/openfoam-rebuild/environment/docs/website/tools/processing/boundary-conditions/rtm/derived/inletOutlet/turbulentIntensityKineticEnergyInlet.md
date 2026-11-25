<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inletOutlet/turbulentIntensityKineticEnergyInlet -->

# turbulentIntensityKineticEnergyInlet

## Description

The `turbulentIntensityKineticEnergyInlet` is a boundary condition that
provides a turbulent kinetic energy condition, based on user\-supplied turbulence
intensity, defined as a fraction of the mean velocity:

kp\=1\.5(I∣u∣)2 k\_p \= 1\.5 (I \|\\u\|)^2kp​\=1\.5(I∣u∣)2
where:

| Property | Description |
| --- | --- |
| kpk\_pkp​ | Kinetic energy at the patch |
| III | Turbulence intensity |
| u\\uu | Velocity field |

In the event of reverse flow, a zero\-gradient condition is applied.

## Usage

The condition requires entries in both the boundary and field files.

### Boundary file

```
<patchName>
{
    type             patch;
    ...
}

```

### Field file

```
<patchName>
{
    // Mandatory entries
    type             turbulentIntensityKineticEnergyInlet;
    intensity        <scalar>;

    // Optional entries
    U               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentIntensityKineticEnergyInlet` | word | yes | \- |
| `intensity` | Fraction of mean field \[0\-1] | scalar | yes | \- |
| `U` | Name of velocity field | word | no | U |

The inherited entries are elaborated in:

* [inletOutletFvPatchFields.H](inletOutlet.md)

## Further information

Tutorial:

* [squareBendLiq](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoSimpleFoam/squareBendLiq)

Source code:

* [turbulentIntensityKineticEnergyInlet](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/turbulentIntensityKineticEnergyInlet)

API:

* [Foam::turbulentIntensityKineticEnergyInletFvPatchScalarField](https://api.openfoam.com/2606/Foam_turbulentIntensityKineticEnergyInletFvPatchScalarField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
