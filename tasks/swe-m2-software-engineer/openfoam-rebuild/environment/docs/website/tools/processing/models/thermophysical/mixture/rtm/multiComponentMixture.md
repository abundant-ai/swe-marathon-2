<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/mixture/rtm/multiComponentMixture -->

# Multi\-component Mixture

The `multiComponentMixture` model describes a single phase mixture that is
defined using individual species.

## Usage

The `multiComponentMixture` model is specified in multiple parts. Firstly, the
`mixture` is set in the top\-level `thermoType` dictionary:

```
thermoType
{
    mixture         multiComponentMixture;
    ...
}

```

Secondly, the list of participating species must then be defined:

```
species         (<list-of-species>);

```

For example, to set nitrogen (N2\) and water (H2O):

```
species         (N2 H2O);

```

Thirdly, each specie must be defined in dictionary format, where the name of
each dictionary is set to each specie name, e.g. following the previous example
with `N2` and `H2O`:

```
N2
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

H2O
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

## Initial conditions

Finally, the user must supply initial fields for each species in the initial
time directories with appropriate field values and boundary conditions, e.g.

```
<case>/0/N2
<case>/0/H2O

```

If multiple species are to be defined using the identical initial conditions,
the `Ydefault` field can be employed to provide generic description, i.e. using

```
<case>/0/Ydefault

```

all species that are not defined will be set according to the `Ydefault`
entries.

## Further information

Source code

* [multiComponentMixture](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/mixtures/multiComponentMixture)

Example usage:

* interFoam `vofToLagrangian` tutorial:
[lagrangianDistributionInjection](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/laminar/vofToLagrangian/lagrangianDistributionInjection)
