<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/mixture/rtm/reactingMixture -->

# Reacting Mixture

The `reactingMixture` model describes a single phase mixture that is
defined using individual, possibly reacting species.

## Usage

The `reactingMixture` is set in the top\-level `thermoType` dictionary:

```
thermoType
{
    mixture         reactingMixture;
    <...>
}

```

Specie and reaction properties are introduced by the `chemistryReader`, e.g.
to specify the `foamChemistryReader`:

```
chemistryReader foamChemistryReader;
foamChemistryFile <path-to-reactions-file>;
foamChemistryThermoFile "path-to-thermophysical-properties-file";

```

For example:

```
chemistryReader foamChemistryReader;
foamChemistryFile "<constant>/reactions";
foamChemistryThermoFile "<constant>/thermo";

```

The `foamChemistryFile` contains entries for:

```
elements        (<list-of-elements>);
species         (<list-of-species>)

reactions
{
    // List of reactions in dictionary format
}

```

The `foamChemistryThermoFile` contains descriptions for each specie whose
requirements depend on the top\-level `thermoType` options
[detailed earlier](../../index.md).

## Initial conditions

See [multiComponentMixture](multiComponentMixture.md#initial-conditions)
initial conditions.

## Further information

Source code

* [reactingMixture](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/mixtures/reactingMixture)

Example usage:

* reactingFoam `counterFlowFlame2D` tutorial:
[counterFlowFlame2D](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/reactingFoam/laminar/counterFlowFlame2D)
