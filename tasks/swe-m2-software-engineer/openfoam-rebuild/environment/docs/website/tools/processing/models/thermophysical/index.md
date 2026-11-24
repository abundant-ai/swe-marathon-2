<!-- https://doc.openfoam.com/2606/tools/processing/models/thermophysical/ -->

# Thermophysical

Thermophysical properties are specified in user\-selectable *packages* that
describe collections of models, based on either compressibility
(ψ\\psiψ, `psi`) or density (ρ\\rhoρ, `rho`).

The system starts with the [specie](specie.md)\-\-\-the most basic entity that
describes information such as the specie name, molecular weight and gas
constant. This is extended by additional models that return thermophysical
properties as functions of pressure and temperature.

Requirements vary according to the
[solver application](../../solvers/index.md), e.g. for single phase,
multiphase, compressibility\- or density\-based, chemical reactions etc.

## Single phase systems

Thermophysical properties for single phase calculations are specified in the
file:

```
$FOAM_CASE/constant/thermophysicalProperties

```

The main `thermoType` dictionary entry defines the set of models used to
describe the system, comprising the entries:

```
thermoType
{
    type            <thermophysical-model>;
    mixture         <mixture-model>;

    transport       <transport-model>;
    thermo          <thermodynamics-model>;
    equationOfState <equation-of-state-model>;
    specie          <specie-model>;

    energy          <energy-model>;
}

```

Here, the `type` entry sets the top\-level thermophysical model type, e.g.

* `hePsiThermo` : compressibility\-based ([source code](https://api.openfoam.com/2606/grpPsiThermo.html))
* `heRhoThermo` : density\-based ([source code](https://api.openfoam.com/2606/grpRhoThermo.html))
* `heheuPsiThermo` : compressibility\-based with extensions for
mixture is burnt/unburnt systems ([source code](https://api.openfoam.com/2606/Foam_heheuPsiThermo.html))
* `heSolidThermo` : solid\-based ([source code](https://api.openfoam.com/2606/Foam_heSolidThermo.html))

The `he` prefix signifies the energy variable that may be based on either
enthalpy (`h`) or internal energy (`e`).

The `mixture` type depends on the solver application; mixtures that can be
approximated by a single component are defined using the `pureMixture` type:

```
mixture         pureMixture;

```

All properties are then defined in a `mixture` sub\-dictionary taking the form:

```
mixture
{
    specie
    {
        ...
    }
    equationOfState
    {
        ...
    }
    thermodynamics
    {
        ...
    }
    transport
    {
        ...
    }
}

```

Each of the `mixture` entries are described in the following sections:

* [Equation of state](equation-of-state/index.md)
* [Thermodynamics](thermodynamics/index.md)
* [Transport](transport/index.md)

Available options for the `energy` entry include:

* absoluteEnthalpy
* absoluteInternalEnergy
* sensibleEnthalpy
* sensibleInternalEnergy

### Multi\-component mixtures

Both reacting and non\-reacting mixtures are supported by some applications.
The required inputs typically follow the pattern described above:

* [Mixture](mixture/index.md)

## Multiphase systems

Each phase is described separately for multiphase systems, using file names
with the convention:

```
$FOAM_CASE/constant/thermophysicalProperties.<phase>

```

## Further information

Source code:

* [thermophysicalModels](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels)
* [Source documentation](https://api.openfoam.com/2606/grpThermophysicalModels.html)
