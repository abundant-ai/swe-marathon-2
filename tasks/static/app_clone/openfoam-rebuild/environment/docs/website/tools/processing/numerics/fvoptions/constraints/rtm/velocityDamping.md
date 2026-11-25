<!-- https://doc.openfoam.com/2606/tools/processing/numerics/fvoptions/constraints/rtm/velocityDamping -->

# Velocity damping

This constraint is primarily used to dampen velocity fluctuations in the
start\-up phase of simulations. When the local velocity exceeds the
user\-supplied maximum value a sink term is activated in the affected region
to lower the velocity to the limiting value.

## Properties

Additional reporting is provided for the number of cells being damped, and as a
percentage of cells over the complete mesh.

When active, this constraint manipulates the system of equations. Users
should ensure that it is not active when the case is converged (steady\-state)
or during the period of interest (transient) to ensure that its presence does
not pollute the results.

## Usage

```
velocityDamping
{
    type            velocityDampingConstraint;
    selectionMode   all;
    UMax            200;
}

```

## Further information

Tutorials

* *none*

Source code

* [velocityDampingConstraint](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/fvOptions/constraints/derived/velocityDampingConstraint)
