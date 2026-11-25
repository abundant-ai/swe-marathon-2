<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/plenumPressure -->

# plenumPressure

## Description

The `plenumPressure` is a pressure boundary condition that provides a
plenum pressure inlet condition. This
condition creates a zero\-dimensional model of an enclosed volume of gas
upstream of the inlet. The pressure that the boundary condition exerts on
the inlet boundary is dependent on the thermodynamic state of the upstream
volume. The upstream plenum density and temperature are time\-stepped along
with the rest of the simulation, and momentum is neglected. The plenum is
supplied with a user specified mass flow and temperature.

The result is a boundary condition which blends between a pressure inlet
condition condition and a fixed mass flow. The smaller the plenum
volume, the quicker the pressure responds to a deviation from the supply
mass flow, and the closer the model approximates a fixed mass flow. As
the plenum size increases, the model becomes more similar to a specified
pressure.

The expansion from the plenum to the inlet boundary is controlled by an
area ratio and a discharge coefficient. The area ratio can be used to
represent further acceleration between a sub\-grid blockage such as fins.
The discharge coefficient represents a fractional deviation from an
ideal expansion process.

This condition is useful for simulating unsteady internal flow problems
for which both a mass flow boundary is unrealistic, and a pressure
boundary is susceptible to flow reversal. It was developed for use in
simulating confined combustion.

References:

```
Bainbridge, W. (2013).
The Numerical Simulation of Oscillations
in Gas Turbine Combustion Chambers,
PhD Thesis,
Chapter 4, Section 4.3.1.2, 77-80.

```

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
    type                plenumPressure;
    gamma               <scalar>;
    R                   <scalar>;
    supplyMassFlowRate  <scalar>;
    supplyTotalTemperature  <scalar>;
    plenumVolume        <scalar>;
    plenumDensity       <scalar>;
    plenumTemperature   <scalar>;
    inletAreaRatio      <scalar>;
    inletDischargeCoefficient  <scalar>;

    // Optional entries
    rho                 <scalar>;.
    timeScale           <scalar>;
    phi                 <word>;
    U                   <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `plenumPressure` | word | yes | \- |
| `gamma` | Ratio of specific heats | scalar | yes | \- |
| `R` | Specific gas constant | scalar | yes | \- |
| `supplyMassFlowRate` | Flow rate into the plenum | scalar | yes | \- |
| `supplyTotalTemperature` | Temperature into the plenum | scalar | yes | \- |
| `plenumVolume` | Plenum volume | scalar | yes | \- |
| `plenumDensity` | Plenum density | scalar | yes | \- |
| `plenumTemperature` | Plenum temperature | scalar | yes | \- |
| `inletAreaRatio` | Inlet open fraction | scalar | yes | \- |
| `inletDischargeCoefficient` | Inlet loss coefficient | scalar | yes | \- |
| `rho` | Inlet density | scalar | no | 1\.0 |
| `timeScale` | Relaxation time scale | scalar | no | 0\.0 |
| `phi` | Name of flux field | scalar | no | phi |
| `U` | Name of velocity field | scalar | no | U |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* [helmholtzResonance](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance)

Source code:

* [plenumPressure](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/plenumPressure)

API:

* [Foam::plenumPressureFvPatchScalarField](https://api.openfoam.com/2606/Foam_plenumPressureFvPatchScalarField.html)

**History:** Introduced in version [v1606\+](https://www.openfoam.com/news/main-news/openfoam-v1606+)
