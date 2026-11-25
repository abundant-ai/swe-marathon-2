<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/general/variableHeightFlowRate -->

# variableHeightFlowRate

## Description

The `variableHeightFlowRate` is a boundary condition that provides
a phase fraction condition based on the local flow conditions, whereby the
values are constrained to lay between user\-specified upper and lower bounds.

The behaviour is described by:

* if alpha \> upperBound:
	+ apply a fixed value condition, with a uniform level of the upper bound
* if lower bound \<\= alpha \<\= upper bound:
	+ apply a zero\-gradient condition
* if alpha \< lowerBound:
	+ apply a fixed value condition, with a uniform level of the lower bound

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
    type            variableHeightFlowRate;
    lowerBound      <scalar>;
    upperBound      <scalar>;

    // Optional entries
    phi             <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `variableHeightFlowRate` | word | yes | \- |
| `lowerBound` | Lower bound for clipping | scalar | yes | \- |
| `upperBound` | Upper bound for clipping | scalar | yes | \- |
| `phi` | Name of flux field | word | no | phi |

The inherited entries are elaborated in:

* mixedFvPatchFields.H

## Further information

Tutorial:

* [weirOverflow](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/multiphase/interFoam/RAS/weirOverflow)

Source code:

* [variableHeightFlowRate](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/variableHeightFlowRate)

API:

* [Foam::variableHeightFlowRateFvPatchField](https://api.openfoam.com/2606/Foam_variableHeightFlowRateFvPatchField.html)

**History:** Introduced in version [2\.1\.1](https://www.openfoam.com/news/main-news/openfoam-2.1.1)
