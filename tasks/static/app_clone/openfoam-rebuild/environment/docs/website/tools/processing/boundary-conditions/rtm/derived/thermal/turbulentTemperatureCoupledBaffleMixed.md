<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/turbulentTemperatureCoupledBaffleMixed -->

# turbulentTemperatureCoupledBaffleMixed

## Description

The `turbulentTemperatureCoupledBaffleMixed` is a boundary condition that provides
a mixed boundary condition for temperature, to be used for heat\-transfer
on back\-to\-back baffles. Optional thin thermal layer resistances can be
specified through `thicknessLayers` and `kappaLayers` entries.

The condition specifies gradient and temperature such that the equations
are the same on both sides:

* refGradient \= zero gradient
* refValue \= neighbour value
* mixFraction \= nbrKDelta / (nbrKDelta \+ myKDelta())

where `KDelta` is heat\-transfer coefficient K \* deltaCoeffs.

The thermal conductivity `kappa` can either be retrieved from various
possible sources, as detailed in the class `temperatureCoupledBase`.

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
    type            compressible::turbulentTemperatureCoupledBaffleMixed;
    Tnbr            <word>;

    // Optional entries
    thicknessLayer  <PatchFunction1<scalar>>;
    kappaLayer      <PatchFunction1<scalar>>;
    thicknessLayers <scalarField>;

    // Conditional entries

        // if 'thicknessLayers' entry is set
        kappaLayers  <scalarField>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentTemperatureCoupledBaffleMixed` | word | yes | \- |
| `Tnbr` | Name of field on the neighbour region | word | yes | \- |
| `thicknessLayer` | Thickness of a single layer | scalarList | no | \- |
| `thicknessLayers` | Thickness of multiple layers | PatchFunction1\<scalar\> | no | \- |
| `kappaLayer` | Conductivity of a single layer | scalarList | no | \- |
| `kappaLayers` | Conductivity of multiple layers | PatchFunction1\<scalar\> | no | \- |

The inherited entries are elaborated in:

* mappedPatchFieldBase.H
* mixedFvPatchFields.H
* temperatureCoupledBase.H

## Further information

Tutorial:

* N/A

Source code:

* [turbulentTemperatureCoupledBaffleMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/turbulentTemperatureCoupledBaffleMixed)

API:

* [Foam::compressible::turbulentTemperatureCoupledBaffleMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_turbulentTemperatureCoupledBaffleMixedFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
