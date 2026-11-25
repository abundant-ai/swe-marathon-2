<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/mixture/ -->

# Mixture

## Options

Mixture model selections include:

Additional non\-documented models (links to API guide):

* [egrMixture](https://api.openfoam.com/2606/Foam_egrMixture.html)
* [homogeneousMixture](https://api.openfoam.com/2606/Foam_homogeneousMixture.html)
* [inhomogeneousMixture](https://api.openfoam.com/2606/Foam_inhomogeneousMixture.html)
* [singleStepReactingMixture](https://api.openfoam.com/2606/Foam_singleStepReactingMixture.html)
* [veryInhomogeneousMixture](https://api.openfoam.com/2606/Foam_veryInhomogeneousMixture.html)

* [Multi\-component Mixture](rtm/multiComponentMixture.md)
* [Pure Mixture](rtm/pureMixture.md)
* [Reacting Mixture](rtm/reactingMixture.md)

## Usage

The mixture type is specified in the `thermoType` dictionary:

```
thermoType
{
    mixture         <model>;
    <...>
}

```

Additional entries will then be required based on the user selection.

## Further information

Source code

* [basicMixture](https://api.openfoam.com/2606/Foam_basicMixture.html)
