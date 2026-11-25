<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/mixture/rtm/pureMixture -->

# Pure Mixture

The `pureMixture` model describes a single phase mixture that can be
approximated by a single component, e.g. an individual specie, approximation
for air etc.

## Usage

The `pureMixture` is set in the top\-level `thermoType` dictionary:

```
thermoType
{
    mixture         pureMixture;
    <...>
}

```

All properties must be defined in a `mixture` sub\-dictionary taking the form:

```
mixture
{
    specie
    {
        <...>
    }
    equationOfState
    {
        <...>
    }
    thermodynamics
    {
        <...>
    }
    transport
    {
        <...>
    }
}

```

where `<...>` entries depend on the top\-level `thermoType` options
[detailed earlier](../../index.md).

## Further information

Source code

* [pureMixture](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/basic/mixtures/pureMixture)
singleStepReactingMixture;
inhomogeneousMixture;
veryInhomogeneousMixture

openfoam/src/thermophysicalModels/reactionThermo/mixtures
egrMixture
inhomogeneousMixture
singleComponentMixture
singleStepReactingMixture
veryInhomogeneousMixture
