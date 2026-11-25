<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/outlet/flowRateOutletVelocity -->

# fluxCorrectedVelocity

## Description

The `fluxCorrectedVelocity` is a velocity\-outlet boundary condition that
for patches where the pressure is specified. The outflow velocity is obtained
by `zeroGradient` and then corrected from the flux.

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
    type            fluxCorrectedVelocity;

    // Conditional entries

        // Option-1
        volumetricFlowRate      <Function1<scalar>>;

        // Option-2
        massFlowRate            <Function1<scalar>>;

    // Optional entries
    rho             <word>;
    rhoOutlet       <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `fluxCorrectedVelocity` | word | yes | \- |
| `volumetricFlowRate` | Volumetric flow rate | Function1\<scalar\> | choice | \- |
| `massFlowRate` | Mass flow rate | Function1\<scalar\> | choice | \- |
| `rho` | Name of density field | word | no | rho |
| `rhoOutlet` | Density initialisation value | scalar | no | \-VGREAT |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)
* [Foam::Function1](https://api.openfoam.com/2606/Foam_Function1.html)

* For a mass\-based flux:
	+ The flow rate should be provided in \[kg/s].
	+ If `rho` is `none` the flow rate is in \[m^3/s].
	+ Otherwise `rho` should correspond to the name of the density field
	+ If the density field cannot be found in the database, the user must

```
specify the outlet density using the `rhoOutlet` entry.

```

* For a volumetric\-based flux:
	+ The flow rate is in \[m^3/s].
* `rhoOutlet` is required for the case of a mass flow rate, where the
density field is not available at start\-up.
* The value is positive out of the domain (as an outlet).
* May not work correctly for transonic outlets.
* Strange behaviour with potentialFoam since the U equation is not solved.

## Further information

Tutorial:

* [iobasin](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interIsoFoam/iobasin)

Source code:

* [fluxCorrectedVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/fluxCorrectedVelocity)

API:

* [Foam::fluxCorrectedVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_fluxCorrectedVelocityFvPatchVectorField.html)

**History:** Introduced in version [v1712](https://www.openfoam.com/news/main-news/openfoam-v1712)
