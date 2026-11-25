<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/flowRateInletVelocity -->

# flowRateInletVelocity

## Description

The `flowRateInletVelocity` is a velocity boundary condition that either
corrects the extrapolated velocity or creates a uniform velocity field normal
to the patch adjusted to match the specified flow rate.
The condition is a wrapper around the [fixedValue](../general/fixedValue.md)
condition.

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
    type                flowRateInletVelocity;

    // Conditional entries

        // Option-1
        volumetricFlowRate  <Function1<scalar>>;

        // Option-2
        massFlowRate        <Function1<scalar>>;

    // Optional entries
    rho                 <word>;
    rhoInlet            <scalar>;
    extrapolateProfile  <bool>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `flowRateInletVelocity` | word | yes | \- |
| `volumetricFlowRate` | Volumetric flow rate | Function1\<scalar\> | choice | \- |
| `massFlowRate` | Mass flow rate | Function1\<scalar\> | choice | \- |
| `rho` | Name of density field | word | no | rho |
| `rhoInlet` | Density initialisation value | scalar | no | \-VGREAT |
| `extrapolateProfile` | Flag to extrapolate the velocity profile from the interior | bool | no | false |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* For a mass\-based flux input:
	+ The flow rate should be provided in \[kg/s].
	+ If `rho` is `none` the flow rate is in \[m^3/s].
	+ Otherwise `rho` should correspond to the name of the density field
	+ If the density field cannot be found in the database, the user must

```
specify the inlet density using the `rhoInlet` entry.

```

* For a volumetric\-based flux:
	+ The flow rate is in \[m^3/s].

A uniform plug flow is set by default. To set the profile according to the
downstream cells:

```
extrapolateProfile  yes;

```

To convert from a mass flow rate to a volumetric flow rate:

```
rho                 rho;

```

To convert from a mass flow rate to a volumetric flow rate for incompressible
flows:

```
rhoInlet            1.0;

```

## Further information

Tutorial:

* [helmholtzResonance](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/compressible/rhoPimpleFoam/laminar/helmholtzResonance)
* [angledDuct](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/incompressible/porousSimpleFoam/angledDuct)

Source code:

* [flowRateInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/flowRateInletVelocity)

API:

* [Foam::flowRateInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_flowRateInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
