<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/pressurePIDControlInletVelocity -->

# pressurePIDControlInletVelocity

## Description

The `pressurePIDControlInletVelocity` is a velocity boundary condition that
tries to generate an inlet velocity that maintains
a specified pressure drop between two face zones downstream. The zones
should fully span a duct through which all the inlet flow passes.

An incompressible, lossless analysis of the flow between the inlet and the
two face\-zones is performed. An ideal inlet velocity is thereby calculated
from the user\-specified pressure drop. This analysis can include the
transient effect of the inlet velocity change. In this case, a shape factor
is included to represent non\-linearity in the duct cross section.

The average pressure drop between the two face zones is measured. The same
incompressible, lossless analysis is performed using this pressure drop.
The difference between the two computed velocities is considered as an
error. The ideal inlet is modified so as to drive this error to zero. This
is accomplished by means of a PID control algorithm, for which
non\-dimensional gains are specified by the user.

The shape factor takes a value of 0 for a linear change in cross sectional
area between the two face zones. A value of 1 represents a step change in
area at the mid\-point between the zones. A smooth cubic or cosine profile
between two zones with zero divergence is typically represented by a factor
of between 0\.2 and 0\.25\.

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
    type                pressurePIDControlInletVelocity;
    upstream            <word>;
    downstream          <word>;
    deltaP              <scalar>;
    P                   <scalar>;
    I                   <scalar>;
    D                   <scalar>;

    // Optional entries
    shapeFactor         <scalar>;
    p                   <word>;
    phi                 <word>;
    rho                 <word>;
    error               <scalar>;
    errorIntegral       <scalar>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `pressurePIDControlInletVelocity` | word | yes | \- |
| `upstream` | Name of the upstream face zone | word | yes | \- |
| `downstream` | Name of the downstream face zone | word | yes | \- |
| `deltaP` | Desired pressure difference between upstream and downstream | scalar | yes | \- |
| `P` | Proportional gain | scalar | yes | \- |
| `I` | Integral gain | scalar | yes | \- |
| `D` | Derivative gain | scalar | yes | \- |
| `shapeFactor` | Nozzle shape factor | scalar | no | 0\.0 |
| `phi` | Name of flux field | word | no | phi |
| `rho` | Name of density field | word | no | rho |
| `error` | Error | scalar | no | 0\.0 |
| `errorIntegral` | Error integral wrt time | scalar | no | 0\.0 |

The inherited entries are elaborated in:

* [Foam::fixedValueFvPatchField](https://api.openfoam.com/2606/Foam_fixedValueFvPatchField.html)

## Further information

Tutorial:

* N/A

Source code:

* [pressurePIDControlInletVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/pressurePIDControlInletVelocity)

API:

* [Foam::pressurePIDControlInletVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_pressurePIDControlInletVelocityFvPatchVectorField.html)

**History:** Introduced in version [v3\.0\+](https://www.openfoam.com/news/main-news/openfoam-v3.0+)
