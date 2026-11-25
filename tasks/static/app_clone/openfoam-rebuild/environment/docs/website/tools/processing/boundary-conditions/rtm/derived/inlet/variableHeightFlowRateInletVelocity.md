<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/variableHeightFlowRateInletVelocity -->

# variableHeightFlowRateInletVelocity

## Description

The `variableHeightFlowRateInletVelocity` is a boundary condition that provides
a velocity boundary condition for multphase flow based on a user\-specified
volumetric flow rate.

The flow rate is made proportional to the phase fraction alpha at each
face of the patch and alpha is ensured to be bound between 0 and 1\.

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
    type            variableHeightFlowRateInletVelocity;
    flowRate        <Function1<scalar>>;
    alpha           <word>;

    // Inherited entries;
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `variableHeightFlowRateInletVelocity` | word | yes | \- |
| `flowRate` | Volumetric flow rate \[m^3/s] | Function1\<scalar\> | yes | \- |
| `alpha` | Name of phase\-fraction field | word | no | alpha |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H
* Function1\.H

* The value is positive into the domain.
* The condition may not work correctly for transonic inlets.
* Strange behaviour with [potentialFoam](../../../../solvers/rtm/basic/potentialFoam.md) since the
momentum equation is not solved.

## Further information

Tutorial:

* [weirOverflow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/weirOverflow)

Source code:

* [variableHeightFlowRateInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/variableHeightFlowRateInletVelocity)

API:

* [Foam::variableHeightFlowRateInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_variableHeightFlowRateInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
