<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/thermal/speciesSorption -->

# speciesSorption

## Description

The `speciesSorption` is a boundary condition that provides
a first\-order zero\-gradient condition for a given scalar field to
model time\-dependent adsorption\-desorption processes.

dcdt\=kads(ceq−cabs) \\frac{d c}{d t} \= k\_{ads} (c\_{eq} \- c\_{abs})dtdc​\=kads​(ceq​−cabs​)
where:

| Property | Description |
| --- | --- |
| ceqc\_{eq}ceq​ | Equilibrium concentration |
| cabsc\_{abs}cabs​ | Absorbed at wall |
| kadsk\_{ads}kads​ | Adsorption rate constant \[1/s] |

ceq\=cmaxkl cint1\+kl cint c\_{eq} \= c\_{max} \\frac{k\_l \\, c\_{int}}{1 \+ k\_l \\, c\_{int}}ceq​\=cmax​1\+kl​cint​kl​cint​​
where:

| Property | Description |
| --- | --- |
| cmaxc\_{max}cmax​ | Maximum concentration |
| klk\_lkl​ | Langmuir constant |
| cintc\_{int}cint​ | Local cell value concentration |

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
    type                    speciesSorption;
    equilibriumModel        <word>;
    kinematicModel          <word>;
    kabs                    <scalar>;
    kl                      <scalar>;
    max                     <scalar>;
    thickness               <PatchFunction1<scalar>>;
    rhoS                    <scalar>;

    // Optional entries
    dfldp                   <scalarField>;
    mass                    <scalarField>;
    pName                   <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `speciesSorption` | word | yes | \- |
| `equilibriumModel` | Equilibrium model | word | yes | \- |
| `kinematicModel` | Kinematic model | word | yes | \- |
| `kabs` | Adsorption rate constant \[1/s] | scalar | yes | \- |
| `kl` | Langmuir constant \[1/Pa] | scalar | yes | \- |
| `max` | Maximum concentation at wall \[mol/kg] | scalar | yes | \- |
| `thickness` | Solid thickness along the patch | PatchFunction1\<scalar\> | yes | \- |
| `rhoS` | Solid density | scalar | yes | \- |
| `dfldp` | Source on cells next to patch | scalarField | no | Zero |
| `mass` | Absorbed mass per kg of absorbent \[mol/kg] | scalarField | no | Zero |
| `pName` | Name of operand pressure field | word | no | p |

Options for the `equilibriumModel` entry:

| Property | Description |
| --- | --- |
| `Langmuir` | Langmuir model |

Options for the `kinematicModel` entry:

| Property | Description |
| --- | --- |
| `PseudoFirstOrder` | Pseudo first\-order model |

The inherited entries are elaborated in:

* zeroGradientFvPatchFields.H
* PatchFunction1\.H
* boundarySourcePatch.H

## Further information

Tutorial:

* [groundAbsorption](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/rhoReactingFoam/groundAbsorption)

Source code:

* [speciesSorption](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/thermophysicalModels/reactionThermo/derivedFvPatchFields/speciesSorption)

API:

* [Foam::speciesSorptionFvPatchScalarField](https://api.openfoam.com/2606/Foam_speciesSorptionFvPatchScalarField.html)

**History:** Introduced in version [v2112](https://www.openfoam.com/news/main-news/openfoam-v2112)
