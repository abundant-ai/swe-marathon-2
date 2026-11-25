<!-- https://doc.openfoam.com/2606/tools/processing/boundary-conditions/rtm/derived/inlet/activePressureForceBaffleVelocity -->

# activePressureForceBaffleVelocity

## Description

The `activePressureForceBaffleVelocity` is a velocity boundary condition to
simulate the opening or closure of a baffle due to area averaged pressure or
force delta, between both sides of the baffle. This is achieved by merging the
behaviours of wall and cyclic baffles.

## Usage

The condition requires entries in both the `boundary` and field files.

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
    type            activePressureForceBaffleVelocity;
    cyclicPatch     <word>;
    openFraction    <scalar>;
    openingTime     <scalar>;
    maxOpenFractionDelta <scalar>;
    minThresholdValue <scalar>;
    forceBased      <bool>;
    opening         <bool>;

    // Optional entries
    p               <word>;

    // Inherited entries
    ...
}

```

where:

| Property | Description | Type | Required | Default |
| --- | --- | --- | --- | --- |
| `type` | Type name: `activePressureForceBaffleVelocity` | word | yes | \- |
| `cyclicPatch` | Name of cyclic patch used when the active baffle is open | word | yes | \- |
| `openFraction` | Current fraction of the active baffle which is open | scalar | yes | \- |
| `openingTime` | Time taken for the active baffle to open | scalar | yes | \- |
| `maxOpenFractionDelta` | Maximum fractional change to the active baffle openness per time step | scalar | yes | \- |
| `minThresholdValue` | Minimum value for the active baffle to start opening | scalar | yes | \- |
| `forceBased` | Flag to activate force based baffle | bool | yes | \- |
| `opening` | Flag to decide if baffle is opening or closing (1 opening, 0 closing) | bool | yes | \- |
| `p` | Name of pressure field | word | no | p |

The inherited entries are elaborated in:

* fixedValueFvPatchField.H

## Method

The baffle joins two mesh regions, where the open fraction determines
the interpolation weights applied to each cyclic\- and neighbour\-patch
contribution. This means that this is boundary condition is meant to be
used in an extra wall beyond an existing cyclic patch pair.

The baffle is activated when the area weighted pressure difference between
master and slave patches is larger then `minThresholdValue`.

Once the threshold is crossed, the baffle is activated and continues to
open or close at a fixed rate using:

x\=xold\+s×dtDT x \= x\_{old} \+ s \\times \\frac{dt}{DT}x\=xold​\+s×DTdt​
where:

| Property | Description |
| --- | --- |
| xxx | Baffle open fraction \[0\-1] |
| xoldx\_{old}xold​ | Baffle open fraction on previous evaluation |
| sss | Sign for orientation: 1 to open or \-1 to close |
| dtdtdt | Simulation time step |
| DTDTDT | Time taken to open the baffle |

The open fraction is then applied to scale the patch areas.

## Further information

Tutorial:

* [flamePropagationWithObstacles](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/tutorials/combustion/PDRFoam/flamePropagationWithObstacles)

Source code:

* [activePressureForceBaffleVelocity](https://gitlab.com/openfoam/core/openfoam/-/tree/OpenFOAM-v2606/src/finiteVolume/fields/fvPatchFields/derived/activePressureForceBaffleVelocity)

API:

* [Foam::activePressureForceBaffleVelocityFvPatchVectorField](https://api.openfoam.com/2606/Foam_activePressureForceBaffleVelocityFvPatchVectorField.html)

**History:** Introduced in version [1\.5](https://www.openfoam.com/news/main-news/openfoam-1.5)
