<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/turbulentTemperatureRadCoupledMixed -->

# turbulentTemperatureRadCoupledMixed

## Description

The `turbulentTemperatureRadCoupledMixed` is a boundary condition that provides
a mixed boundary condition for temperature, to be used for heat\-transfer
on back\-to\-back baffles. Optional thin thermal layer resistances can be
specified through `thicknessLayers` and `kappaLayers` entries.

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
    type            compressible::turbulentTemperatureRadCoupledMixed;
    Tnbr            <word>;

    // Optional entries
    Tnbr                <word>;
    qrNbr               <word>;
    qr                  <word>;
    logInterval         <scalar>;
    thermalInertia      <bool>;
    verbose             <bool>;
    prefix              <word>;

    // Conditional entries

        // Option-1
        thicknessLayers <scalarList>;
        kappaLayers     <scalarList>;

        // Option-2
        thicknessLayer  <PatchFunction1<scalar>>;
        kappaLayer      <PatchFunction1<scalar>>;

    // Inherited entries
    kappaMethod         <word>;
    kappa               <word>;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `turbulentTemperatureRadCoupledMixed` | word | yes | \- |
| `Tnbr` | Name of field on the neighbour region | word | yes | \- |
| `thicknessLayer` | Thickness of a single layer | scalarList | no | \- |
| `thicknessLayers` | Thickness of multiple layers | PatchFunction1\<scalar\> | no | \- |
| `kappaLayer` | Conductivity of a single layer | scalarList | no | \- |
| `kappaLayers` | Conductivity of multiple layers | PatchFunction1\<scalar\> | no | \- |
| `Tnbr` | Name of the nbr temperature field | word | no | T |
| `qrNbr` | Name of the radiative flux in the nbr region | word | no | none |
| `qr` | Name of the radiative flux in this region | word | no | none |
| `logInterval` | Log\-file output frequency \[s] | scalar | no | \-1 |
| `thermalInertia` | Flag to add thermal inertia to wall node | bool | no | false |
| `verbose` | Flag to enable verbose output with extra fields | bool | no | false |
| `prefix` | Name of output\-field prefix (in verbose mode) | word | no | multiWorld |

The inherited entries are elaborated in:

* mappedPatchFieldBase.H
* mixedFvPatchFields.H
* temperatureCoupledBase.H
* writeFile.H

## Further information

Tutorial:

* [2DImplicitCyclic](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/basic/chtMultiRegionFoam/2DImplicitCyclic)

Source code:

* [turbulentTemperatureRadCoupledMixed](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermoTools/derivedFvPatchFields/turbulentTemperatureRadCoupledMixed)

API:

* [Foam::compressible::turbulentTemperatureRadCoupledMixedFvPatchScalarField](https://api.openfoam.com/2606/Foam_compressible_turbulentTemperatureRadCoupledMixedFvPatchScalarField.html)

**History:** Introduced in version [v2206](https://www.openfoam.com/news/main-news/openfoam-v2206)
